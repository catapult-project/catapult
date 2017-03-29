# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue which deprecates TestMetadata, kicks off jobs to delete old
row data, and create StoppageAlerts when tests stop sending data for an extended
period of time.
"""

import datetime
import logging

from google.appengine.api import taskqueue
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import ndb

from dashboard import layered_cache
from dashboard import list_tests
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import stoppage_alert

# Length of time required to pass for a test to be considered deprecated.
_DEPRECATION_REVISION_DELTA = datetime.timedelta(days=14)

# Length of time required to pass for a test to be deleted entirely.
_REMOVAL_REVISON_DELTA = datetime.timedelta(days=183)

_DELETE_TASK_QUEUE_NAME = 'delete-tests-queue'

_DEPRECATE_TESTS_TASK_QUEUE_NAME = 'deprecate-tests-queue'

_DEPRECATE_TESTS_PER_QUERY = 100


class DeprecateTestsHandler(request_handler.RequestHandler):
  """Handler to run a deprecate tests job."""

  def get(self):
    queue_stats = taskqueue.QueueStatistics.fetch(
        [_DEPRECATE_TESTS_TASK_QUEUE_NAME])

    if not queue_stats:
      logging.error('Failed to fetch QueueStatistics.')
      return

    # Check if the queue has tasks which would indicate there's an
    # existing job still running.
    if queue_stats[0].tasks and not queue_stats[0].in_flight:
      logging.info('Did not start /deprecate_tests, ' +
                   'previous one still running.')
      return

    taskqueue.add(
        url='/deprecate_tests',
        queue_name=_DEPRECATE_TESTS_TASK_QUEUE_NAME)

  def post(self):
    datastore_hooks.SetPrivilegedRequest()
    self._DeprecateTestsTask()

  @ndb.synctasklet
  def _DeprecateTestsTask(self):
    start_cursor = self.request.get('start_cursor', None)
    if start_cursor:
      start_cursor = Cursor(urlsafe=start_cursor)

    query = graph_data.TestMetadata.query()
    query.filter(graph_data.TestMetadata.has_rows == True)
    query.order(graph_data.TestMetadata.key)
    keys, next_cursor, more = yield query.fetch_page_async(
        _DEPRECATE_TESTS_PER_QUERY, start_cursor=start_cursor,
        keys_only=True)

    if more:
      taskqueue.add(
          url='/deprecate_tests',
          params={
              'start_cursor': next_cursor.urlsafe()
          },
          queue_name=_DEPRECATE_TESTS_TASK_QUEUE_NAME)

    yield [_DeprecateTest(k) for k in keys]


@ndb.tasklet
def _DeprecateTest(entity_key):
  """Marks a TestMetadata entity as deprecated if the last row is too old.

  What is considered "too old" is defined by _DEPRECATION_REVISION_DELTA. Also,
  if all of the subtests in a test have been marked as deprecated, then that
  parent test will be marked as deprecated.

  This mapper doesn't un-deprecate tests if new data has been added; that
  happens in add_point.py.

  Args:
    entity: The TestMetadata entity to check.
  """
  # Fetch the last row.
  entity = yield entity_key.get_async()
  query = graph_data.Row.query(
      graph_data.Row.parent_test == utils.OldStyleTestKey(entity.key))
  query = query.order(-graph_data.Row.timestamp)
  last_row = yield query.get_async()

  # Check if the test should be deleted entirely.
  now = datetime.datetime.now()
  logging.info('checking %s', entity.test_path)
  if not last_row or last_row.timestamp < now - _REMOVAL_REVISON_DELTA:
    # descendants = list_tests.GetTestDescendants(entity.key, keys_only=True)
    child_paths = '/'.join([entity.key.id(), '*'])
    descendants = yield list_tests.GetTestsMatchingPatternAsync(child_paths)

    if entity.key in descendants:
      descendants.remove(entity.key)
    if not descendants:
      logging.info('removing')
      if last_row:
        logging.info('last row timestamp: %s', last_row.timestamp)
      else:
        logging.info('no last row, no descendants')

      _AddDeleteTestDataTask(entity)
      return

  if entity.deprecated:
    return

  if not last_row:
    yield _CheckAndMarkSuiteDeprecated(entity)
    return

  if last_row.timestamp < now - _DEPRECATION_REVISION_DELTA:
    yield _MarkTestDeprecated(entity)

  yield _CreateStoppageAlerts(entity, last_row)


def _IsRef(test):
  if test.test_path.endswith('/ref') or test.test_path.endswith('_ref'):
    return True
  return False


def _AddDeleteTestDataTask(entity):
  taskqueue.add(
      url='/delete_test_data',
      params={
          'test_path': utils.TestPath(entity.key),  # For manual inspection.
          'test_key': entity.key.urlsafe(),
          'notify': 'false',
      },
      queue_name=_DELETE_TASK_QUEUE_NAME)


@ndb.tasklet
def _CreateStoppageAlerts(test, last_row):
  """Creates a StoppageAlert for the test, if needed.

  A stoppage alert is an alert created to warn people that data has not
  been received for a particular test for some length of time. An alert
  will only be created if the stoppage_alert_delay property of the sheriff
  is non-zero -- the value of this property is the number of days that should
  pass before an alert is created.

  Args:
    test: A TestMetadata entity.
    last_row: The Row entity that was last added.
  """
  if not test.sheriff or _IsRef(test):
    return
  sheriff_entity = yield test.sheriff.get_async()
  warn_sheriff_delay_days = sheriff_entity.stoppage_alert_delay
  if warn_sheriff_delay_days < 0:
    return
  now = datetime.datetime.now()
  warn_sheriff_delta = datetime.timedelta(days=warn_sheriff_delay_days)
  earliest_warn_time = now - warn_sheriff_delta
  if last_row.timestamp >= earliest_warn_time:
    return
  if stoppage_alert.GetStoppageAlert(test.test_path, last_row.revision):
    return
  new_alert = stoppage_alert.CreateStoppageAlert(test, last_row)
  if not new_alert:
    return
  yield new_alert.put_async()


@ndb.tasklet
def _MarkTestDeprecated(test):
  """Marks a TestMetadata as deprecated and clears any related cached data."""
  test.deprecated = True
  yield (
      test.put_async(),
      _DeleteCachedTestData(test))


@ndb.tasklet
def _CheckAndMarkSuiteDeprecated(suite):
  """Marks a TestMetadata suite as deprecated if all it's children are
  also deprecated, and clears related cached data."""
  # If this is a suite, check if we can deprecate the entire suite
  if len(suite.key.id().split('/')) == 3:
    # Check whether the test suite now contains only deprecated tests, and
    # if so, deprecate it too.
    all_deprecated = yield _AllSubtestsDeprecated(suite)
    if all_deprecated:
      suite.deprecated = True
      yield (
          suite.put_async(),
          _DeleteCachedTestData(suite))


@ndb.tasklet
def _DeleteCachedTestData(test):
  # The sub-test listing function returns different results depending
  # on whether tests are deprecated, so when a new suite is deprecated,
  # the cache needs to be cleared.
  yield layered_cache.DeleteAsync(graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
      test.master_name, test.bot_name, test.suite_name))


@ndb.tasklet
def _AllSubtestsDeprecated(test):
  descendant_tests = yield list_tests.GetTestDescendantsAsync(
      test.key, has_rows=True, keys_only=False)
  result = all(t.deprecated for t in descendant_tests)
  raise ndb.Return(result)
