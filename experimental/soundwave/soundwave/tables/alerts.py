# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pandas  # pylint: disable=import-error


COLUMNS = (
    'key',  # string: unique datastore key ('agxzfmNocm9tZXBlcmZyFAsS')
    'timestamp',  # np.datetime64: time and date when the alert was created
    'test_suite',  # string: benchmark name ('loading.mobile')
    'measurement',  # string: metric name ('timeToFirstContentfulPaint')
    'bot',  # string: master/builder name ('ChromiumPerf.android-nexus5')
    'test_case',  # string: story name ('Wikipedia')
    'start_revision',  # string: git hash or commit position before anomaly
    'end_revision',  # string: git hash or commit position after anomaly
    'median_before_anomaly',  # float: median of values recorded before anomaly
    'median_after_anomaly',  # float: median of values recorded after anomaly
    'units',  # string: unit in which values are masured ('ms')
    'improvement',  # boolean: whether anomaly is an improvement or regression
    'bug_id',  # int: crbug number associated with this alert, 0 if missing
    'status',  # string: one of 'ignored', 'invalid', 'triaged', 'untriaged'
    'bisect_status',  # string: one of 'started', 'falied', 'completed'
)
INDEX = COLUMNS[0]


_CODE_TO_STATUS = {
    -2: 'ignored',
    -1: 'invalid',
    None: 'untriaged',
    # Any positive integer represents a bug_id and maps to a 'triaged' status.
}


def RowFromJson(data):
  """Turn json data from an alert into a tuple with values for that record."""
  data = data.copy()  # Do not modify the original dict.

  # Name fields using newer dashboard nomenclature.
  data['test_suite'] = data.pop('testsuite')
  data['measurement'], data['test_case'] = data.pop('test').split('/', 1)
  data['bot'] = '/'.join([data.pop('master'), data.pop('bot')])

  # Separate bug_id from alert status.
  data['status'] = _CODE_TO_STATUS.get(data['bug_id'], 'triaged')
  if data['status'] == 'triaged':
    assert data['bug_id'] > 0
  else:
    # pandas cannot hold both int and None values in the same series, if so the
    # type is coerced into float; to prevent this we use 0 to denote untriaged
    # alerts with no bug_id assigned.
    data['bug_id'] = 0

  return tuple(data[k] for k in COLUMNS)


def DataFrameFromJson(data):
  df = pandas.DataFrame.from_records(
      (RowFromJson(d) for d in data['anomalies']), index=INDEX, columns=COLUMNS)
  df['timestamp'] = pandas.to_datetime(df['timestamp'])
  return df
