# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for the main page which lists recent anomalies and bugs."""

import datetime
import json
import logging
import urllib

from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.ext import ndb

from dashboard import email_template
from dashboard import request_handler
from dashboard import utils
from dashboard.models import anomaly

_ANOMALY_FETCH_LIMIT = 1000
_DEFAULT_DAYS_TO_SHOW = 7
_DEFAULT_CHANGES_TO_SHOW = 10
_DEFAULT_SHERIFF_NAME = 'Chromium Perf Sheriff'


class MainHandler(request_handler.RequestHandler):
  """Displays the main overview page."""

  def get(self):
    """Renders the UI for the main overview page.

    The purpose of this page is to show recent regressions and improvements,
    as well as recently-filed bugs.

    Request parameters:
      days: Number of days to show anomalies and bugs for (optional).
      sheriff: Sheriff to show anomalies for (optional)
      num_changes: The number of improvements/regressions to list.

    Outputs:
      A HTML page that shows recent regressions, improvements and bugs.
    """
    days = int(self.request.get('days', _DEFAULT_DAYS_TO_SHOW))
    num_changes = int(self.request.get('num_changes', _DEFAULT_CHANGES_TO_SHOW))
    sheriff_name = self.request.get('sheriff', _DEFAULT_SHERIFF_NAME)
    sheriff = ndb.Key('Sheriff', sheriff_name)

    top_bugs_rpc = _TopBugsUrlFetch(days)
    anomalies = _GetRecentAnomalies(days, sheriff)
    top_bugs = _GetTopBugsResult(top_bugs_rpc)

    top_improvements = _TopImprovements(anomalies, num_changes)
    top_regressions = _TopRegressions(anomalies, num_changes)
    tests = _GetKeyToTestDict(top_improvements + top_regressions)

    template_dict = {
        'num_days': days,
        'num_changes': num_changes,
        'sheriff_name': sheriff_name,
        'improvements': _AnomalyInfoDicts(top_improvements, tests),
        'regressions': _AnomalyInfoDicts(top_regressions, tests),
        'bugs': top_bugs,
    }
    self.RenderHtml('main.html', template_dict)


def _GetRecentAnomalies(days, sheriff):
  """Fetches recent Anomalies from the datastore.

  Args:
    days: Number of days old of the oldest Anomalies to fetch.
    sheriff: The ndb.Key of the Sheriff to fetch Anomalies for.

  Returns:
    A list of Anomaly entities sorted from large to small relative change.
  """
  oldest_time = datetime.datetime.now() - datetime.timedelta(days=days)
  anomalies_query = anomaly.Anomaly.query(
      anomaly.Anomaly.timestamp > oldest_time,
      anomaly.Anomaly.sheriff == sheriff)
  anomalies = anomalies_query.fetch(limit=_ANOMALY_FETCH_LIMIT)
  anomalies.sort(key=lambda a: abs(a.percent_changed), reverse=True)
  # We only want to list alerts that aren't marked invalid or ignored.
  anomalies = [a for a in anomalies if a.bug_id is None or a.bug_id > 0]
  return anomalies


def _GetKeyToTestDict(anomalies):
  """Returns a map of Test keys to entities for the given anomalies."""
  test_keys = {a.test for a in anomalies}
  tests = utils.GetMulti(test_keys)
  return {t.key: t for t in tests}


def _GetColorClass(percent_changed):
  """Returns a CSS class name for the anomaly, based on percent changed."""
  if percent_changed > 50:
    return 'over-50'
  if percent_changed > 40:
    return 'over-40'
  if percent_changed > 30:
    return 'over-30'
  if percent_changed > 20:
    return 'over-20'
  if percent_changed > 10:
    return 'over-10'
  return 'under-10'


def _AnomalyInfoDicts(anomalies, tests):
  """Returns information info about the given anomalies.

  Args:
    anomalies: A list of anomalies.
    tests: A dictionary mapping Test keys to Test entities.

  Returns:
    A list of dictionaries with information about the given anomalies.
  """
  anomaly_list = []
  for anomaly_entity in anomalies:
    # TODO(qyearsley): Add test coverage. See http://crbug.com/447432
    test = tests.get(anomaly_entity.test)
    if not test:
      logging.warning('No Test entity for key: %s.', anomaly_entity.test)
      continue
    subtest_path = '/'.join(test.test_path.split('/')[3:])
    graph_link = email_template.GetGroupReportPageLink(anomaly_entity)
    anomaly_list.append({
        'key': anomaly_entity.key.urlsafe(),
        'bug_id': anomaly_entity.bug_id or '',
        'start_revision': anomaly_entity.start_revision,
        'end_revision': anomaly_entity.end_revision,
        'master': test.master_name,
        'bot': test.bot_name,
        'testsuite': test.suite_name,
        'test': subtest_path,
        'percent_changed': anomaly_entity.GetDisplayPercentChanged(),
        'color_class': _GetColorClass(abs(anomaly_entity.percent_changed)),
        'improvement': anomaly_entity.is_improvement,
        'dashboard_link': graph_link,
    })
  return anomaly_list


def _TopImprovements(recent_anomalies, num_to_show):
  """Fills in the given template dictionary with top improvements.

  Args:
    recent_anomalies: A list of Anomaly entities sorted from large to small.
    num_to_show: The number of improvements to return.

  Returns:
    A list of top improvement Anomaly entities, in decreasing order.
  """
  improvements = [a for a in recent_anomalies if a.is_improvement]
  return improvements[:num_to_show]


def _TopRegressions(recent_anomalies, num_to_show):
  """Fills in the given template dictionary with top regressions.

  Args:
    recent_anomalies: A list of Anomaly entities sorted from large to small.
    num_to_show: The number of regressions to return.

  Returns:
    A list of top regression Anomaly entities, in decreasing order.
  """
  regressions = [a for a in recent_anomalies if not a.is_improvement]
  return regressions[:num_to_show]


def _TopBugsUrlFetch(days):
  """Makes asychronous fetch for top bugs.

  Args:
    days: Number of days, as an integer.

  Returns:
    An RPC object of asynchronous request.
  """
  query_url = _GetQueryUrl(days)
  rpc = urlfetch.create_rpc(deadline=5)
  urlfetch.make_fetch_call(rpc, query_url)
  return rpc


def _GetTopBugsResult(rpc):
  """Gets a dictionary with recent bug information.

  Args:
    rpc: RPC object of asynchronous request.

  Returns:
    A list of dictionaries with information about bugs, or [] if no list
    could be fetched.
  """
  try:
    response = rpc.get_result()
    if response.status_code == 200:
      bugs = json.loads(response.content)
      if bugs and bugs.get('items'):
        return bugs['items']
  except urlfetch_errors.DeadlineExceededError:
    pass
  except urlfetch.DownloadError:
    pass
  return []


def _GetQueryUrl(days):
  """Returns the URL to query for bugs.

  Args:
    days: Number of days as an integer.

  Returns:
    A URL which can be used to request information about recent bugs.
  """
  base_url = ('https://www.googleapis.com'
              '/projecthosting/v2/projects/chromium/issues?')
  query_string = urllib.urlencode({
      'q': ('label:Type-Bug-Regression label:Performance '
            'opened-after:today-%d' % days),
      'fields': 'items(id,state,status,summary,author)',
      'maxResults': '1000',
      'sort': '-id',
      'can': 'all',
      'key': 'AIzaSyDrEBALf59D7TkOuz-bBuOnN2OqzD70NCQ',
  })
  return base_url + query_string
