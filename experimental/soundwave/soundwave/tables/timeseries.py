# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pandas  # pylint: disable=import-error

from soundwave import pandas_sqlite


TABLE_NAME = 'timeseries'
COLUMN_TYPES = (
    # Index columns.
    ('test_suite', str),  # benchmark name ('loading.mobile')
    ('measurement', str),  # metric name ('timeToFirstContentfulPaint')
    ('bot', str),  # master/builder name ('ChromiumPerf.android-nexus5')
    ('test_case', str),  # story name ('Wikipedia')
    ('point_id', 'int64'),  # monotonically increasing value for time series axis
    # Other columns.
    ('value', 'float64'),  # value recorded for test_path at given point_id
    ('timestamp', 'datetime64[ns]'),  # when the value got stored on dashboard
    ('commit_pos', 'int64'),  # chromium commit position
    ('chromium_rev', str),  # git hash of chromium revision
    ('clank_rev', str),  # git hash of clank revision
    ('improvement_direction', str),  # good direction ('up', 'down', 'unknown')
)
COLUMNS = tuple(c for c, _ in COLUMN_TYPES)
INDEX = COLUMNS[:5]


# Copied from https://goo.gl/DzGYpW.
_CODE_TO_IMPROVEMENT_DIRECTION = {
    0: 'up',
    1: 'down',
}


TEST_PATH_PARTS = (
    'master', 'builder', 'test_suite', 'measurement', 'test_case')

# Query template to find all data points of a given test_path (i.e. fixed
# test_suite, measurement, bot, and test_case values).
_QUERY_TIME_SERIES = (
    'SELECT * FROM %s WHERE %s'
    % (TABLE_NAME, ' AND '.join('%s=?' % c for c in INDEX[:-1])))


def DataFrame(rows=None):
  return pandas_sqlite.DataFrame(COLUMN_TYPES, index=INDEX, rows=rows)


def _ParseIntValue(value, on_error=-1):
  # Try to parse as int and, in case of error, return a pre-defined value.
  try:
    return int(value)
  except StandardError:
    return on_error


def _ParseConfigFromTestPath(test_path):
  values = test_path.split('/', len(TEST_PATH_PARTS) - 1)
  if len(values) < len(TEST_PATH_PARTS):
    values.append('')  # Possibly missing test_case.
  if len(values) != len(TEST_PATH_PARTS):
    raise ValueError(test_path)
  config = dict(zip(TEST_PATH_PARTS, values))
  config['bot'] = '%s/%s' % (config.pop('master'), config.pop('builder'))
  return config


def DataFrameFromJson(data):
  config = _ParseConfigFromTestPath(data['test_path'])
  config['improvement_direction'] = _CODE_TO_IMPROVEMENT_DIRECTION.get(
      data['improvement_direction'], 'unknown')
  timeseries = data['timeseries']
  # The first element in timeseries list contains header with column names.
  header = timeseries[0]
  rows = []

  # Remaining elements contain the values for each row.
  for values in timeseries[1:]:
    row = config.copy()
    row.update(zip(header, values))
    row['point_id'] = row['revision']
    row['commit_pos'] = _ParseIntValue(row['r_commit_pos'])
    row['chromium_rev'] = row.get('r_chromium')
    row['clank_rev'] = row.get('r_clank', None)
    rows.append(tuple(row.get(k) for k in COLUMNS))

  return DataFrame(rows)


def GetTimeSeries(con, test_path, extra_cond=None):
  """Get the records for all data points on the given test_path.

  Returns:
    A pandas.DataFrame with all records found.
  """
  config = _ParseConfigFromTestPath(test_path)
  params = tuple(config[c] for c in INDEX[:-1])
  query = _QUERY_TIME_SERIES
  if extra_cond is not None:
    query = ' '.join([query, extra_cond])
  return pandas.read_sql(query, con, params=params, parse_dates=['timestamp'])


def GetMostRecentPoint(con, test_path):
  """Find the record for the most recent data point on the given test_path.

  Returns:
    A pandas.Series with the record if found, or None otherwise.
  """
  df = GetTimeSeries(con, test_path, 'ORDER BY timestamp DESC LIMIT 1')
  return df.iloc[0] if not df.empty else None
