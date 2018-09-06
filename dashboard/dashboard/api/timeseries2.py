# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard import alerts
from dashboard.api import api_request_handler
from dashboard.api import utils as api_utils
from dashboard.common import descriptor
from dashboard.common import timing
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import histogram


# These limits should prevent DeadlineExceededErrors.
# TODO(benjhayden): Find a better strategy for staying under the deadline.
DIAGNOSTICS_QUERY_LIMIT = 10000
HISTOGRAMS_QUERY_LIMIT = 1000
ROWS_QUERY_LIMIT = 20000

COLUMNS_REQUIRING_ROWS = {'timestamp', 'revisions'}.union(descriptor.STATISTICS)
CACHE_SECONDS = 60 * 60 * 24 * 7


class Timeseries2Handler(api_request_handler.ApiRequestHandler):

  def _AllowAnonymous(self):
    return True

  def AuthorizedPost(self):
    desc = descriptor.Descriptor(
        test_suite=self.request.get('test_suite'),
        measurement=self.request.get('measurement'),
        bot=self.request.get('bot'),
        test_case=self.request.get('test_case'),
        statistic=None,
        build_type=self.request.get('build_type'))
    min_revision = self.request.get('min_revision')
    min_revision = int(min_revision) if min_revision else None
    max_revision = self.request.get('max_revision')
    max_revision = int(max_revision) if max_revision else None
    query = TimeseriesQuery(
        desc, self.request.get('columns').split(','),
        min_revision, max_revision,
        api_utils.ParseISO8601(self.request.get('min_timestamp', None)),
        api_utils.ParseISO8601(self.request.get('max_timestamp', None)))
    try:
      result = query.FetchSync()
    except AssertionError:
      # The caller has requested internal-only data but is not authorized.
      raise api_request_handler.NotFoundError
    self.response.headers['Cache-Control'] = '%s, max-age=%d' % (
        'private' if query.private else 'public', CACHE_SECONDS)
    return result


class TimeseriesQuery(object):

  def __init__(self, desc, columns, min_revision=None, max_revision=None,
               min_timestamp=None, max_timestamp=None):
    self._descriptor = desc
    self._columns = columns
    self._min_revision = min_revision
    self._max_revision = max_revision
    self._min_timestamp = min_timestamp
    self._max_timestamp = max_timestamp
    self._statistic_columns = []
    self._unsuffixed_test_metadata_keys = []
    self._test_keys = []
    self._units = None
    self._improvement_direction = None
    self._data = {}
    self._private = False

  @property
  def private(self):
    return self._private

  @timing.TimeWall('fetch')
  @timing.TimeCpu('fetch')
  def FetchSync(self):
    return self.FetchAsync().get_result()

  @ndb.tasklet
  def FetchAsync(self):
    """Returns {units, improvement_direction, data}.

    Raises:
      api_request_handler.NotFoundError when the timeseries cannot be found.
      AssertionError when an external user requests internal-only data.
    """
    # Always need to query TestMetadata even if the caller doesn't need units
    # and improvement_direction because Row doesn't have internal_only.
    # Use tasklets so that they can process the data as it arrives.
    self._CreateTestKeys()
    futures = [self._FetchTests()]
    if COLUMNS_REQUIRING_ROWS.intersection(self._columns):
      futures.append(self._FetchRows())
    elif 'histogram' in self._columns:
      futures.append(self._FetchHistograms())
    if 'alert' in self._columns:
      self._ResolveTimestamps()
      futures.append(self._FetchAlerts())
    if 'diagnostics' in self._columns:
      self._ResolveTimestamps()
      futures.append(self._FetchDiagnostics())
    yield futures
    raise ndb.Return({
        'units': self._units,
        'improvement_direction': self._improvement_direction,
        'data': [[datum.get(col) for col in self._columns]
                 for _, datum in sorted(self._data.iteritems())],
    })

  def _ResolveTimestamps(self):
    if self._min_timestamp and self._min_revision is None:
      self._min_revision = self._ResolveTimestamp(self._min_timestamp)
    if self._max_timestamp and self._max_revision is None:
      self._max_revision = self._ResolveTimestamp(self._max_timestamp)

  def _ResolveTimestamp(self, timestamp):
    query = graph_data.Row.query(
        graph_data.Row.parent_test.IN(self._test_keys),
        graph_data.Row.timestamp <= timestamp)
    query = query.order(-graph_data.Row.timestamp)
    row_keys = query.fetch(1, keys_only=True)
    if not row_keys:
      return None
    return row_keys[0].integer_id()

  def _CreateTestKeys(self):
    desc = self._descriptor.Clone()

    desc.statistic = None
    unsuffixed_test_paths = desc.ToTestPathsSync()
    self._unsuffixed_test_metadata_keys = [
        utils.TestMetadataKey(path) for path in unsuffixed_test_paths]

    self._statistic_columns = [
        col for col in self._columns if col in descriptor.STATISTICS]
    test_paths = []
    for statistic in self._statistic_columns:
      desc.statistic = statistic
      test_paths.extend(desc.ToTestPathsSync())

    test_metadata_keys = [utils.TestMetadataKey(path) for path in test_paths]
    test_metadata_keys.extend(self._unsuffixed_test_metadata_keys)
    test_paths.extend(unsuffixed_test_paths)

    test_old_keys = [utils.OldStyleTestKey(path) for path in test_paths]
    self._test_keys = test_old_keys + test_metadata_keys

  @ndb.tasklet
  def _FetchTests(self):
    with timing.WallTimeLogger('fetch_tests'):
      tests = yield [key.get_async() for key in self._test_keys]
    tests = [test for test in tests if test]
    if not tests:
      raise api_request_handler.NotFoundError

    improvement_direction = None
    for test in tests:
      if test.internal_only:
        self._private = True

      test_desc = yield descriptor.Descriptor.FromTestPathAsync(
          utils.TestPath(test.key))
      # The unit for 'count' statistics is trivially always 'count'. Callers
      # certainly want the units of the measurement, which is the same as the
      # units of the 'avg' and 'std' statistics.
      if self._units is None or test_desc.statistic != 'count':
        self._units = test.units
        improvement_direction = test.improvement_direction

    if improvement_direction == anomaly.DOWN:
      self._improvement_direction = 'down'
    elif improvement_direction == anomaly.UP:
      self._improvement_direction = 'up'
    else:
      self._improvement_direction = None

  def _Datum(self, revision):
    return self._data.setdefault(revision, {'revision': revision})

  @ndb.tasklet
  def _FetchRows(self):
    yield [self._FetchRowsForTest(test_key) for test_key in self._test_keys]

  @staticmethod
  def Round(x):
    return round(x, 6)

  def _RowQueryProjection(self, statistic):
    limit = ROWS_QUERY_LIMIT
    projection = None

    # 'r_'-prefixed revisions are not in any index, so a projection query can't
    # get them.
    if 'revisions' in self._columns:
      return projection, limit

    # There is no index like (parent_test, -timestamp, revision, value):
    self._ResolveTimestamps()

    # If statistic is not None, then project value. _CreateTestKeys will
    # generate test keys for the other statistics in columns if there are any.
    # If statistic is None and the only statistic is avg, then project value.
    # If statistic is None and there are multiple statistics, then fetch full
    # Row entities because we might need their 'error' aka 'std' or
    # 'd_'-prefixed statistics.
    if ((statistic is not None) or
        (','.join(self._statistic_columns) == 'avg')):
      projection = ['revision', 'value']
      if 'timestamp' in self._columns:
        projection.append('timestamp')
      limit = None

    return projection, limit

  @ndb.tasklet
  def _FetchRowsForTest(self, test_key):
    test_desc = yield descriptor.Descriptor.FromTestPathAsync(
        utils.TestPath(test_key))
    projection, limit = self._RowQueryProjection(test_desc.statistic)
    query = graph_data.Row.query(projection=projection)
    query = query.filter(graph_data.Row.parent_test == test_key)
    query = self._FilterRowQuery(query)

    with timing.WallTimeLogger('fetch_test'):
      rows = yield query.fetch_async(limit)

    with timing.CpuTimeLogger('rows'):
      for row in rows:
        # Sometimes the dev environment just ignores some filters.
        if self._min_revision and row.revision < self._min_revision:
          continue
        if self._min_timestamp and row.timestamp < self._min_timestamp:
          continue
        if self._max_revision and row.revision > self._max_revision:
          continue
        if self._max_timestamp and row.timestamp > self._max_timestamp:
          continue
        datum = self._Datum(row.revision)
        if test_desc.statistic is None:
          datum['avg'] = self.Round(row.value)
          if hasattr(row, 'error') and row.error:
            datum['std'] = self.Round(row.error)
        else:
          datum[test_desc.statistic] = self.Round(row.value)
        for stat in self._statistic_columns:
          if hasattr(row, 'd_' + stat):
            datum[stat] = self.Round(getattr(row, 'd_' + stat))
        if 'timestamp' in self._columns:
          datum['timestamp'] = row.timestamp.isoformat()
        if 'revisions' in self._columns:
          datum['revisions'] = {
              attr: value for attr, value in row.to_dict().iteritems()
              if attr.startswith('r_')}

    if 'histogram' in self._columns and test_desc.statistic == None:
      with timing.WallTimeLogger('fetch_histograms'):
        yield [self._FetchHistogram(test_key, row.revision) for row in rows]

  def _FilterRowQuery(self, query):
    if self._min_revision or self._max_revision:
      if self._min_revision:
        query = query.filter(graph_data.Row.revision >= self._min_revision)
      if self._max_revision:
        query = query.filter(graph_data.Row.revision <= self._max_revision)
      query = query.order(-graph_data.Row.revision)
    elif self._min_timestamp or self._max_timestamp:
      if self._min_timestamp:
        query = query.filter(graph_data.Row.timestamp >= self._min_timestamp)
      if self._max_timestamp:
        query = query.filter(graph_data.Row.timestamp <= self._max_timestamp)
      query = query.order(-graph_data.Row.timestamp)
    else:
      query = query.order(-graph_data.Row.revision)
    return query

  @ndb.tasklet
  def _FetchAlerts(self):
    anomalies, _, _ = yield anomaly.Anomaly.QueryAsync(
        test_keys=self._test_keys,
        max_start_revision=self._max_revision,
        min_end_revision=self._min_revision)
    for alert in anomalies:
      if alert.internal_only:
        self._private = True
      datum = self._Datum(alert.end_revision)
      # TODO(benjhayden) bisect_status
      datum['alert'] = alerts.GetAnomalyDict(alert)

  @ndb.tasklet
  def _FetchHistograms(self):
    yield [self._FetchHistogramsForTest(test) for test in self._test_keys]

  @ndb.tasklet
  def _FetchHistogramsForTest(self, test):
    query = graph_data.Row.query(graph_data.Row.parent_test == test)
    query = self._FilterRowQuery(query)
    with timing.WallTimeLogger('fetch_histograms'):
      row_keys = yield query.fetch_async(HISTOGRAMS_QUERY_LIMIT, keys_only=True)
      yield [self._FetchHistogram(test, row_key.integer_id())
             for row_key in row_keys]

  @ndb.tasklet
  def _FetchHistogram(self, test, revision):
    query = histogram.Histogram.query(
        histogram.Histogram.test == utils.TestMetadataKey(test),
        histogram.Histogram.revision == revision)
    hist = yield query.get_async()
    if hist is None:
      return
    if hist.internal_only:
      self._private = True
    self._Datum(hist.revision)['histogram'] = hist.data

  @ndb.tasklet
  def _FetchDiagnostics(self):
    with timing.WallTimeLogger('fetch_diagnosticss'):
      yield [self._FetchDiagnosticsForTest(test)
             for test in self._unsuffixed_test_metadata_keys]

  @ndb.tasklet
  def _FetchDiagnosticsForTest(self, test):
    query = histogram.SparseDiagnostic.query(
        histogram.SparseDiagnostic.test == test)
    if self._min_revision:
      query = query.filter(
          histogram.SparseDiagnostic.start_revision >= self._min_revision)
    if self._max_revision:
      query = query.filter(
          histogram.SparseDiagnostic.start_revision <= self._max_revision)
    query = query.order(-histogram.SparseDiagnostic.start_revision)
    diagnostics = yield query.fetch_async(DIAGNOSTICS_QUERY_LIMIT)
    for diag in diagnostics:
      if diag.internal_only:
        self._private = True
      datum = self._Datum(diag.start_revision)
      datum_diags = datum.setdefault('diagnostics', {})
      datum_diags[diag.name] = diag.data
