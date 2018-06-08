# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import time
import urllib

from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

from dashboard import alerts
from dashboard import group_report
from dashboard.api import api_request_handler
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly


ISO_8601_FORMAT = '%Y-%m-%dT%H:%M:%S'


def _InequalityFilters(query, inequality_property,
                       min_end_revision, max_end_revision,
                       min_start_revision, max_start_revision,
                       min_timestamp, max_timestamp):
  # A query cannot have more than one inequality filter.
  # inequality_property allows users to decide which property to filter in the
  # query, which can significantly affect performance. If other inequalities are
  # specified, they will be handled by post_filters.

  # If callers set inequality_property without actually specifying a
  # corresponding inequality filter, then reset the inequality_property and
  # compute it automatically as if it were not specified.
  if inequality_property == 'start_revision':
    if min_start_revision is None and max_start_revision is None:
      inequality_property = None
  elif inequality_property == 'end_revision':
    if min_end_revision is None and max_end_revision is None:
      inequality_property = None
  elif inequality_property == 'timestamp':
    if min_timestamp is None and max_timestamp is None:
      inequality_property = None
  else:
    inequality_property = None

  if inequality_property is None:
    # Compute a default inequality_property.
    if min_start_revision or max_start_revision:
      inequality_property = 'start_revision'
    elif min_end_revision or max_end_revision:
      inequality_property = 'end_revision'
    elif min_timestamp or max_timestamp:
      inequality_property = 'timestamp'

  post_filters = []
  if not inequality_property:
    return query, post_filters

  if min_start_revision:
    min_start_revision = int(min_start_revision)
    if inequality_property == 'start_revision':
      logging.info('filter:min_start_revision=%d', min_start_revision)
      query = query.filter(anomaly.Anomaly.start_revision >= min_start_revision)
      query = query.order(-anomaly.Anomaly.start_revision)
    else:
      post_filters.append(lambda a: a.start_revision >= min_start_revision)

  if max_start_revision:
    max_start_revision = int(max_start_revision)
    if inequality_property == 'start_revision':
      logging.info('filter:max_start_revision=%d', max_start_revision)
      query = query.filter(anomaly.Anomaly.start_revision <= max_start_revision)
      query = query.order(-anomaly.Anomaly.start_revision)
    else:
      post_filters.append(lambda a: a.start_revision <= max_start_revision)

  if min_end_revision:
    min_end_revision = int(min_end_revision)
    if inequality_property == 'end_revision':
      logging.info('filter:min_end_revision=%d', min_end_revision)
      query = query.filter(anomaly.Anomaly.end_revision >= min_end_revision)
      query = query.order(-anomaly.Anomaly.end_revision)
    else:
      post_filters.append(lambda a: a.end_revision >= min_end_revision)

  if max_end_revision:
    max_end_revision = int(max_end_revision)
    if inequality_property == 'end_revision':
      logging.info('filter:max_end_revision=%d', max_end_revision)
      query = query.filter(anomaly.Anomaly.end_revision <= max_end_revision)
      query = query.order(-anomaly.Anomaly.end_revision)
    else:
      post_filters.append(lambda a: a.end_revision <= max_end_revision)

  if min_timestamp:
    min_timestamp = datetime.datetime.strptime(min_timestamp, ISO_8601_FORMAT)
    if inequality_property == 'timestamp':
      logging.info('filter:min_timestamp=%d', min_timestamp)
      query = query.filter(anomaly.Anomaly.timestamp >= min_timestamp)
    else:
      post_filters.append(lambda a: a.timestamp >= min_timestamp)

  if max_timestamp:
    max_timestamp = datetime.datetime.strptime(max_timestamp, ISO_8601_FORMAT)
    if inequality_property == 'timestamp':
      logging.info('filter:max_timestamp=%d', max_timestamp)
      query = query.filter(anomaly.Anomaly.timestamp <= max_timestamp)
    else:
      post_filters.append(lambda a: a.timestamp <= max_timestamp)

  return query, post_filters


def QueryAnomalies(
    bot_name=None,
    bug_id=None,
    inequality_property=None,
    is_improvement=None,
    key=None,
    limit=100,
    master_name=None,
    max_end_revision=None,
    max_start_revision=None,
    max_timestamp=None,
    min_end_revision=None,
    min_start_revision=None,
    min_timestamp=None,
    recovered=None,
    sheriff=None,
    start_cursor=None,
    test=None,
    test_suite_name=None):
  if key:
    logging.info('key')
    try:
      return [ndb.Key(urlsafe=key).get()], None
    except AssertionError:
      return [], None

  query = anomaly.Anomaly.query()
  if sheriff is not None:
    sheriff_key = ndb.Key('Sheriff', sheriff)
    sheriff_entity = sheriff_key.get()
    if not sheriff_entity:
      raise api_request_handler.BadRequestError('Invalid sheriff %s' % sheriff)
    logging.info('filter:sheriff=%s', sheriff)
    query = query.filter(anomaly.Anomaly.sheriff == sheriff_key)
  if is_improvement is not None:
    logging.info('filter:is_improvement=%r', is_improvement)
    query = query.filter(anomaly.Anomaly.is_improvement == is_improvement)
  if bug_id is not None:
    if bug_id == '':
      bug_id = None
    else:
      bug_id = int(bug_id)
    logging.info('filter:bug_id=%r', bug_id)
    query = query.filter(anomaly.Anomaly.bug_id == bug_id)
  if recovered is not None:
    logging.info('filter:recovered=%r', recovered)
    query = query.filter(anomaly.Anomaly.recovered == recovered)
  if test:
    logging.info('filter:test=%s', test)
    query = query.filter(anomaly.Anomaly.test == utils.TestMetadataKey(test))
  if master_name:
    logging.info('filter:master=%s', master_name)
    query = query.filter(anomaly.Anomaly.master_name == master_name)
  if bot_name:
    logging.info('filter:bot_name=%s', bot_name)
    query = query.filter(anomaly.Anomaly.bot_name == bot_name)
  if test_suite_name:
    logging.info('filter:test_suite=%s', test_suite_name)
    query = query.filter(anomaly.Anomaly.benchmark_name == test_suite_name)
  # TODO measurement_name, test_case name

  query, post_filters = _InequalityFilters(
      query, inequality_property, min_end_revision, max_end_revision,
      min_start_revision, max_start_revision, min_timestamp, max_timestamp)
  query = query.order(-anomaly.Anomaly.timestamp)

  if start_cursor:
    logging.info('start_cursor')
  else:
    start_cursor = None

  start = time.time()
  results, next_cursor, more = query.fetch_page(
      limit, start_cursor=start_cursor)
  duration = time.time() - start
  logging.info('query_duration=%f', duration)
  logging.info('query_results_count=%d', len(results))
  logging.info('duration_per_result=%f', duration / len(results))
  if post_filters:
    logging.info('post_filters_count=%d', len(post_filters))
    results = [alert for alert in results
               if all(post_filter(alert) for post_filter in post_filters)]
    logging.info('filtered_results_count=%d', len(results))
  if more:
    logging.info('more')
  else:
    next_cursor = None
  return results, next_cursor


def QueryAnomaliesUntilFound(
    bot_name=None,
    bug_id=None,
    deadline_seconds=50,
    inequality_property=None,
    is_improvement=None,
    key=None,
    limit=100,
    master_name=None,
    max_end_revision=None,
    max_start_revision=None,
    max_timestamp=None,
    min_end_revision=None,
    min_start_revision=None,
    min_timestamp=None,
    recovered=None,
    sheriff=None,
    start_cursor=None,
    test=None,
    test_suite_name=None):
  # post_filters can cause alert_list to be empty, depending on the shape of the
  # data and which filters are applied in the query and which filters are
  # applied after the query. Automatically chase cursors until some results are
  # found, but stay under the request timeout.
  alert_list = []
  deadline = time.time() + deadline_seconds
  while not alert_list and time.time() < deadline:
    alert_list, start_cursor = QueryAnomalies(
        bot_name=bot_name,
        bug_id=bug_id,
        inequality_property=inequality_property,
        is_improvement=is_improvement,
        key=key,
        limit=limit,
        master_name=master_name,
        max_end_revision=max_end_revision,
        max_start_revision=max_start_revision,
        max_timestamp=max_timestamp,
        min_end_revision=min_end_revision,
        min_start_revision=min_start_revision,
        min_timestamp=min_timestamp,
        recovered=recovered,
        sheriff=sheriff,
        start_cursor=start_cursor,
        test=test,
        test_suite_name=test_suite_name)
    if not start_cursor:
      break
  return alert_list, start_cursor


class AlertsHandler(api_request_handler.ApiRequestHandler):
  """API handler for various alert requests."""

  def AuthorizedPost(self, *args):
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
        is_improvement = self.request.get('is_improvement', None)
        assert is_improvement in [None, 'true', 'false'], is_improvement
        if is_improvement:
          is_improvement = is_improvement == 'true'
        recovered = self.request.get('recovered', None)
        assert recovered in [None, 'true', 'false'], recovered
        if recovered:
          recovered = recovered == 'true'
        start_cursor = self.request.get('cursor', None)
        if start_cursor:
          start_cursor = datastore_query.Cursor(urlsafe=start_cursor)

        alert_list, next_cursor = QueryAnomaliesUntilFound(
            bot_name=self.request.get('bot', None),
            bug_id=self.request.get('bug_id', None),
            is_improvement=is_improvement,
            key=self.request.get('key', None),
            limit=int(self.request.get('limit', 100)),
            master_name=self.request.get('master', None),
            max_end_revision=self.request.get('max_end_revision', None),
            max_start_revision=self.request.get('max_start_revision', None),
            max_timestamp=self.request.get('max_timestamp', None),
            min_end_revision=self.request.get('min_end_revision', None),
            min_start_revision=self.request.get('min_start_revision', None),
            min_timestamp=self.request.get('min_timestamp', None),
            recovered=recovered,
            sheriff=self.request.get('sheriff', None),
            start_cursor=start_cursor,
            test=self.request.get('test', None),
            test_suite_name=self.request.get('test_suite', None))
        if next_cursor:
          response['next_cursor'] = next_cursor.urlsafe()
      else:
        list_type = args[0]
        if list_type.startswith('bug_id'):
          bug_id = list_type.replace('bug_id/', '')
          response['DEPRECATION WARNING'] = (
              'Please use /api/alerts?bug_id=%s' % bug_id)
          alert_list = group_report.GetAlertsWithBugId(bug_id)
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
          query = anomaly.Anomaly.query(anomaly.Anomaly.sheriff == sheriff_key)
          query = query.filter(anomaly.Anomaly.timestamp > cutoff)
          if not include_improvements:
            query = query.filter(
                anomaly.Anomaly.is_improvement == False)
            response['DEPRECATION WARNING'] += '&is_improvement=false'
          if filter_for_benchmark:
            query = query.filter(
                anomaly.Anomaly.benchmark_name == filter_for_benchmark)
            response['DEPRECATION WARNING'] += (
                '&test_suite_name=' + filter_for_benchmark)

          query = query.order(-anomaly.Anomaly.timestamp)
          alert_list = query.fetch()
        else:
          raise api_request_handler.BadRequestError(
              'Invalid alert type %s' % list_type)
    except request_handler.InvalidInputError as e:
      raise api_request_handler.BadRequestError(e.message)

    anomaly_dicts = alerts.AnomalyDicts(
        [a for a in alert_list if a.key.kind() == 'Anomaly'])

    response['anomalies'] = anomaly_dicts

    return response
