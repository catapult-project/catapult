# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handler to serve a simple time series for all points in a series.

This is used to show the revision slider for a chart; it includes data
for all past points, including those that are not recent. Each entry
in the returned list is a 3-item list: [revision, value, timestamp].
The revisions and values are used to plot a mini-chart, and the timestamps
are used to label this mini-chart with dates.

This list is cached, since querying all Row entities for a given test takes a
long time. This module also provides a function for updating the cache.
"""

import bisect
import json

from dashboard import datastore_hooks
from dashboard import namespaced_stored_object
from dashboard import request_handler
from dashboard import utils
from dashboard.models import graph_data

_CACHE_KEY = 'num_revisions_%s'


class GraphRevisionsHandler(request_handler.RequestHandler):
  """URL endpoint to list all the revisions for each test, for x-axis slider."""

  def post(self):
    """Fetches a list of revisions and values for a given test.

    Request parameters:
      test_path: Full test path for a TestMetadata entity.

    Outputs:
      A JSON list of 3-item lists [revision, value, timestamp].
    """
    test_path = self.request.get('test_path')
    rows = namespaced_stored_object.Get(_CACHE_KEY % test_path)
    if not rows:
      rows = _UpdateCache(utils.TestKey(test_path))
    self.response.out.write(json.dumps(rows))


def SetCache(test_path, rows):
  """Sets the saved graph revisions data for a test.

  Args:
    test_path: A test path string.
    rows: A list of [revision, value, timestamp] triplets.
  """
  # This first set generally only sets the internal-only cache.
  namespaced_stored_object.Set(_CACHE_KEY % test_path, rows)

  # If this is an internal_only query for externally available data,
  # set the cache for that too.
  if datastore_hooks.IsUnalteredQueryPermitted():
    test = utils.TestKey(test_path).get()
    if test and not test.internal_only:
      namespaced_stored_object.SetExternal(_CACHE_KEY % test_path, rows)


def DeleteCache(test_path):
  """Removes any saved data for the given path."""
  namespaced_stored_object.Delete(_CACHE_KEY % test_path)


def _UpdateCache(test_key):
  """Queries Rows for a test then updates the cache.

  Args:
    test_key: ndb.Key for a TestMetadata entity.

  Returns:
    The list of triplets that was just fetched and set in the cache.
  """
  test = test_key.get()
  if not test:
    return []
  assert utils.IsInternalUser() or not test.internal_only
  datastore_hooks.SetSinglePrivilegedRequest()

  # A projection query queries just for the values of particular properties;
  # this is faster than querying for whole entities.
  query = graph_data.Row.query(projection=['revision', 'value', 'timestamp'])
  query = query.filter(
      graph_data.Row.parent_test == utils.OldStyleTestKey(test_key))

  # Using a large batch_size speeds up queries with > 1000 Rows.
  rows = map(_MakeTriplet, query.iter(batch_size=1000))
  # Note: Unit tests do not call datastore_hooks with the above query, but
  # it is called in production and with more recent SDK.
  datastore_hooks.CancelSinglePrivilegedRequest()
  SetCache(utils.TestPath(test_key), rows)
  return rows


def _MakeTriplet(row):
  """Makes a 3-item list of revision, value and timestamp for a Row."""
  timestamp = utils.TimestampMilliseconds(row.timestamp)
  return [row.revision, row.value, timestamp]


def AddRowsToCache(row_entities):
  """Adds a list of rows to the cache, in revision order.

  Updates multiple cache entries for different tests.

  Args:
    row_entities: List of Row entities.
  """
  test_key_to_rows = {}
  for row in row_entities:
    test_key = row.parent_test
    if test_key in test_key_to_rows:
      graph_rows = test_key_to_rows[test_key]
    else:
      test_path = utils.TestPath(test_key)
      graph_rows = namespaced_stored_object.Get(_CACHE_KEY % test_path)
      if not graph_rows:
        # We only want to update caches for tests that people have looked at.
        continue
      test_key_to_rows[test_key] = graph_rows

    revisions = [r[0] for r in graph_rows]
    index = bisect.bisect_left(revisions, row.revision)
    if index < len(revisions) - 1:
      if revisions[index + 1] == row.revision:
        return  # Already in cache.
    graph_rows.insert(index, _MakeTriplet(row))

  for test_key in test_key_to_rows:
    graph_rows = test_key_to_rows[test_key]
    SetCache(utils.TestPath(test_key), graph_rows)
