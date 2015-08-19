# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Change some Row entities with timestamp IDs to have IDs < 300000.

This is based on cl/71187034 and is intended to be temporary.

Background:
Historically, chromium.webrtc and chromium.webrtc.fyi had sent data with
timestamps for x-values. In the future, they plan to switch to using
commit positions as x-values, but want to keep all of the existing data
there, in order.

Therefore, we want to change all revision numbers of points under the
ChromiumWebRTC and ChromiumWebRTCFYI masters to use modified x-values.

TODO(qyearsley): Remove this handler (and its related entries in BUILD and
dispatcher.py) when http://crbug.com/496048 (and http://crbug.com/469523)
are fixed.
"""

import logging

from google.appengine.api import taskqueue
from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

from dashboard import graph_revisions
from dashboard import request_handler
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data

# Properties that shouldn't be copied when copying rows.
_ROW_EXCLUDE_PROPERTIES = ['parent_test', 'revision', 'id']

# Number of tests and rows to process at once.
_NUM_TESTS = 5
_NUM_ROWS = 600
_NUM_ALERTS = 10

# Minimum number that's considered a timestamp.
_MIN_TIMESTAMP = 100000000

# Task queue that tasks will be pushed onto.
_QUEUE_NAME = 'migrate-queue'


def _ConvertTimestamp(timestamp_seconds):
  """Converts from a timestamp to some new x-value.

  Requirements:
   - Order doesn't change.
   - All resulting x-values are below 300000.
   - It's OK if some timestamps map to the same output values.

  Note: 1356998400 is 2013-01-01 00:00 GMT.
  Generally the points are 1-2 hours apart.
  June 4 2015 is 1433378000, and 1433378000 / (2 * 60 * 60) = 199080.

  Args:
    timestamp_seconds: A Unix timestamp (seconds since 1970).

  Returns:
    A number that can be used as the new point ID for a point.
  """
  return (timestamp_seconds - 1356998400) / (2 * 60 * 60)


class ShrinkTimestampRevisionsHandler(request_handler.RequestHandler):

  def post(self):
    self.get()

  def get(self):
    """Fixes rows for one or more tests and queues the next task to fix more.

    Request parameters:
      ancestor: A slash-separated path to the ancestor to start from.
      cursor: An urlsafe string for a datastore_query.Cursor object.

    Outputs:
      Some indication of the results.
    """
    # Get the ancestor of the tests to change, and abort if not given.
    ancestor = self.request.get('ancestor')
    if not ancestor:
      self.ReportError('Missing ancestor parameter.')
      return
    ancestor_key = utils.TestKey(ancestor)

    # Get the query cursor if given.
    urlsafe_cursor = self.request.get('cursor')
    cursor = None
    if urlsafe_cursor:
      cursor = datastore_query.Cursor(urlsafe=urlsafe_cursor)
    more = False

    test_query = graph_data.Test.query(ancestor=ancestor_key)
    test_query = test_query.filter(
        graph_data.Test.has_rows == True)
    keys, next_cursor, more = test_query.fetch_page(
        _NUM_TESTS, keys_only=True, start_cursor=cursor)

    futures = []
    for key in keys:
      futures.extend(_FixTest(key))
    ndb.Future.wait_all(futures)

    if not futures:
      cursor = next_cursor

    urlsafe_cursor = cursor.urlsafe() if cursor else ''
    if more or futures:
      taskqueue.add(
          queue_name=_QUEUE_NAME,
          url='/shrink_timestamp_revisions',
          params={'cursor': urlsafe_cursor or '', 'ancestor': ancestor})
      logging.info('Task added, cursor: %s', urlsafe_cursor)

    # Display some information, to verify that something is happening.
    self.RenderHtml('result.html', {
        'results': [{'name': 'cursor', 'value': urlsafe_cursor}]
    })


def _FixTest(test_key):
  """Changes Row and Anomaly entities from using timestamps to SVN revisions."""
  futures = _MoveRowsForTest(test_key)
  futures.extend(_UpdateAlertsForTest(test_key))

  # Clear graph revisions cache. This is done so that the cached data
  # will not be inconsistent with the actual data.
  graph_revisions.DeleteCache(utils.TestPath(test_key))
  return futures


def _MoveRowsForTest(test_key):
  """Moves rows for the given test."""
  row_query = graph_data.Row.query(
      graph_data.Row.parent_test == test_key,
      graph_data.Row.revision > _MIN_TIMESTAMP)
  rows = row_query.fetch(limit=_NUM_ROWS)
  test_path = utils.TestPath(test_key)
  logging.info('Moving %d rows for test "%s".', len(rows), test_path)
  to_put = []
  to_delete = []
  for row in rows:
    new_row = _CopyRow(row, _ConvertTimestamp(row.revision))
    to_put.append(new_row)
    to_delete.append(row.key)
  put_futures = ndb.put_multi_async(to_put)
  delete_futures = ndb.delete_multi_async(to_delete)
  return put_futures + delete_futures


def _CopyRow(row, new_revision):
  """Make a copy of the given Row but with a new ID."""
  new_row = graph_data.Row(id=new_revision, parent=row.key.parent())
  create_args = create_args = {
      'id': new_revision,
      'parent': row.key.parent(),
  }
  for prop, val in row.to_dict(exclude=_ROW_EXCLUDE_PROPERTIES).iteritems():
    create_args[prop] = val
  new_row = graph_data.Row(**create_args)
  return new_row


def _UpdateAlertsForTest(test_key):
  """Changes revision properties of alerts."""
  alert_query = anomaly.Anomaly.query(
      anomaly.Anomaly.test == test_key,
      anomaly.Anomaly.end_revision > _MIN_TIMESTAMP)
  alerts = alert_query.fetch(limit=_NUM_ALERTS)
  test_path = utils.TestPath(test_key)
  logging.info('Moving %d alerts in %s', len(alerts), test_path)
  to_put = []
  for a in alerts:
    a.start_revision = _ConvertTimestamp(a.start_revision)
    a.end_revision = _ConvertTimestamp(a.end_revision)
    to_put.append(a)
  return ndb.put_multi_async(to_put)
