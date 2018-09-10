# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import urllib

from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

from dashboard import alerts
from dashboard import group_report
from dashboard.api import api_request_handler
from dashboard.api import utils
from dashboard.common import request_handler
from dashboard.models import anomaly
from dashboard.models import report_template



class AlertsHandler(api_request_handler.ApiRequestHandler):
  """API handler for various alert requests."""

  def _AllowAnonymous(self):
    return True

  def PrivilegedPost(self, *args):
    return self.UnprivilegedPost(*args)

  def UnprivilegedPost(self, *args):
    """Returns alert data in response to API requests.

    Possible list types:
      keys: A comma-separated list of urlsafe Anomaly keys.
      bug_id: A bug number on the Chromium issue tracker.
      rev: A revision number.

    Outputs:
      Alerts data; see README.md.
    """
    alert_list = None
    response = {}
    try:
      if len(args) == 0:
        is_improvement = utils.ParseBool(self.request.get(
            'is_improvement', None))
        recovered = utils.ParseBool(self.request.get('recovered', None))
        start_cursor = self.request.get('cursor', None)
        if start_cursor:
          start_cursor = datastore_query.Cursor(urlsafe=start_cursor)
        min_timestamp = utils.ParseISO8601(self.request.get(
            'min_timestamp', None))
        max_timestamp = utils.ParseISO8601(self.request.get(
            'max_timestamp', None))

        test_keys = []
        for template_id in self.request.get_all('report'):
          test_keys.extend(report_template.TestKeysForReportTemplate(
              template_id))

        try:
          alert_list, next_cursor, _ = anomaly.Anomaly.QueryAsync(
              bot_name=self.request.get('bot', None),
              bug_id=self.request.get('bug_id', None),
              is_improvement=is_improvement,
              key=self.request.get('key', None),
              limit=int(self.request.get('limit', 100)),
              master_name=self.request.get('master', None),
              max_end_revision=self.request.get('max_end_revision', None),
              max_start_revision=self.request.get('max_start_revision', None),
              max_timestamp=max_timestamp,
              min_end_revision=self.request.get('min_end_revision', None),
              min_start_revision=self.request.get('min_start_revision', None),
              min_timestamp=min_timestamp,
              recovered=recovered,
              sheriff=self.request.get('sheriff', None),
              start_cursor=start_cursor,
              test=self.request.get('test', None),
              test_keys=test_keys,
              test_suite_name=self.request.get('test_suite', None)).get_result()
        except AssertionError:
          alert_list, next_cursor = [], None
        if next_cursor:
          response['next_cursor'] = next_cursor.urlsafe()
      else:
        list_type = args[0]
        if list_type.startswith('bug_id'):
          bug_id = list_type.replace('bug_id/', '')
          try:
            bug_id = int(bug_id)
          except ValueError as e:
            raise api_request_handler.BadRequestError(
                'Invalid bug ID "%s".' % bug_id)
          response['DEPRECATION WARNING'] = (
              'Please use /api/alerts?bug_id=%s' % bug_id)
          alert_list, _, _ = anomaly.Anomaly.QueryAsync(
              bug_id=bug_id).get_result()
        elif list_type.startswith('keys'):
          keys = list_type.replace('keys/', '').split(',')
          response['DEPRECATION WARNING'] = (
              'Please use /api/alerts?key=%s' % keys[0])
          alert_list = group_report.GetAlertsForKeys(keys)
        elif list_type.startswith('rev'):
          rev = list_type.replace('rev/', '')
          response['DEPRECATION WARNING'] = (
              'Please use /api/alerts?max_end_revision=%s&min_start_revision=%s'
              % (rev, rev))
          alert_list = group_report.GetAlertsAroundRevision(rev)
        elif list_type.startswith('history'):
          try:
            days = int(list_type.replace('history/', ''))
          except ValueError:
            days = 7
          cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
          sheriff_name = self.request.get('sheriff', 'Chromium Perf Sheriff')
          sheriff_key = ndb.Key('Sheriff', sheriff_name)
          sheriff = sheriff_key.get()
          if not sheriff:
            raise api_request_handler.BadRequestError(
                'Invalid sheriff %s' % sheriff_name)
          response['DEPRECATION WARNING'] = (
              'Please use /api/alerts?min_timestamp=%s&sheriff=%s' % (
                  urllib.quote(cutoff.isoformat()),
                  urllib.quote(sheriff_name)))
          include_improvements = bool(self.request.get('improvements'))
          filter_for_benchmark = self.request.get('benchmark')

          is_improvement = None
          if not include_improvements:
            is_improvement = False
            response['DEPRECATION WARNING'] += '&is_improvement=false'
          if filter_for_benchmark:
            response['DEPRECATION WARNING'] += (
                '&test_suite=' + filter_for_benchmark)

          alert_list, _, _ = anomaly.Anomaly.QueryAsync(
              sheriff=sheriff_key.id(),
              min_timestamp=cutoff,
              is_improvement=is_improvement,
              test_suite_name=filter_for_benchmark).get_result()
        else:
          raise api_request_handler.BadRequestError(
              'Invalid alert type %s' % list_type)
    except AssertionError:
      # The only known assertion is in InternalOnlyModel._post_get_hook when a
      # non-internal user requests an internal-only entity.
      raise api_request_handler.BadRequestError('Not found')
    except request_handler.InvalidInputError as e:
      raise api_request_handler.BadRequestError(e.message)

    anomaly_dicts = alerts.AnomalyDicts(
        [a for a in alert_list if a.key.kind() == 'Anomaly'])

    response['anomalies'] = anomaly_dicts

    return response
