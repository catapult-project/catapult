# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A ReadFromDatastore alternative for fetching entities in a timestamp range.

The main difference from ReadFromDatastore is the query splitting method (for
splitting into parallel fetches).  ReadFromDatastore attempts to automatically
split the query by interrogating the datastore about how best to split the
query.  This strategy fails in many cases, e.g. for huge datasets this initial
query can be prohibitively expensive, and if there's an inequality filter no
splitting is attempted at all.

ReadTimestampRangeFromDatastore simply splits by a timestamp property, which
works well for datasets that are roughly evenly distributed across time (e.g.
most days have roughly the same number of entities).  This only requires a
trivial amount of upfront work, so tends to outperform ReadFromDatastore for
chromeperf's use cases.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime

import apache_beam as beam
from google.cloud.datastore import client as ds_client
from google.cloud.datastore import query as ds_query


class ReadTimestampRangeFromDatastore(beam.PTransform):
  """Similar to ReadFromDatastore; see module docstring."""

  def __init__(self,
               query_params,
               min_timestamp,
               max_timestamp=None,
               step=datetime.timedelta(days=1),
               timestamp_property='timestamp'):
    """Constructor.

    Params:
      :query_params: kwargs for google.cloud.datastore.query.Query's
          constructor.
      :min_timestamp: a datetime.datetime of the lower bound to fetch.
      :max_timestamp: a datetime.dateimte of the upper bound to fetch
          (default is now).
      :step: the interval to split the range to fetch by (default is 1 day).
      :timestamp_property: the name of the timestamp property to filter on.
    """
    super(ReadTimestampRangeFromDatastore, self).__init__()
    self._query_params = query_params
    self._min_timestamp = min_timestamp
    if max_timestamp is None:
      max_timestamp = datetime.datetime.now()
    self._max_timestamp = max_timestamp
    self._step = step
    self._timestamp_property = timestamp_property

  def expand(self, pcoll):  # pylint: disable=invalid-name
    return (pcoll.pipeline
            | 'UserSplits' >> beam.Create(list(self._Splits()))
            | 'ReadRows' >> beam.ParDo(
                ReadTimestampRangeFromDatastore._QueryFn(
                    self._query_params, self._timestamp_property))
           )

  class _QueryFn(beam.DoFn):
    def __init__(self, query_params, timestamp_property):
      super(ReadTimestampRangeFromDatastore._QueryFn, self).__init__()
      self._query_params = query_params
      self._timestamp_property = timestamp_property

    def process(self, start_end, *unused_args,  # pylint: disable=invalid-name
                **unused_kwargs):
      start, end = start_end
      client = ds_client.Client(project=self._query_params['project'])
      query = ds_query.Query(client=client, **self._query_params)
      query.add_filter(self._timestamp_property, '>=', start)
      query.add_filter(self._timestamp_property, '<', end)
      for entity in query.fetch(client=client):
        yield entity

  def _Splits(self):
    start = self._min_timestamp
    while True:
      end = start + self._step
      yield (start, end)

      if end >= self._max_timestamp:
        break
      start = end

