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

    _AddDeprecateTestDataTask({'type': 'fetch-and-process-tests'})

  def post(self):
    datastore_hooks.SetPrivilegedRequest()

    task_type = self.request.get('type')
    if not task_type or task_type == 'fetch-and-process-tests':
      start_cursor = self.request.get('start_cursor', None)
      if start_cursor:
        start_cursor = Cursor(urlsafe=start_cursor)
      _DeprecateTestsTask(start_cursor)
      return

    if task_type == 'deprecate-test':
      test_key = ndb.Key(urlsafe=self.request.get('test_key'))
      _MarkTestDeprecated(test_key)
      return

    if task_type == 'create-stoppage-alert':
      test_key = ndb.Key(urlsafe=self.request.get('test_key'))
      row_key = ndb.Key(urlsafe=self.request.get('row_key'))
      _CreateStoppageAlerts(test_key, row_key)
      return

    logging.error(
        'Unknown task_type posted to /deprecate_tests: %s', task_type)


@ndb.synctasklet
def _DeprecateTestsTask(start_cursor):
  query = graph_data.TestMetadata.query()
  query.filter(graph_data.TestMetadata.has_rows == True)
  query.order(graph_data.TestMetadata.key)
  keys, next_cursor, more = query.fetch_page(
      _DEPRECATE_TESTS_PER_QUERY, start_cursor=start_cursor,
      keys_only=True)

  if more:
    _AddDeprecateTestDataTask({
        'type': 'fetch-and-process-tests',
        'start_cursor': next_cursor.urlsafe()})

  yield [_CheckTestForDeprecationOrRemoval(k) for k in keys]


@ndb.tasklet
def _CheckTestForDeprecationOrRemoval(entity_key):
  """Marks a TestMetadata entity as deprecated if the last row is too old.

  What is considered "too old" is defined by _DEPRECATION_REVISION_DELTA. Also,
  if all of the subtests in a test have been marked as deprecated, then that
  parent test will be marked as deprecated.

  This mapper doesn't un-deprecate tests if new data has been added; that
  happens in add_point.py.

  Args:
    entity: The TestMetadata entity to check.
  Returns:
    A TestMetadata that needs to be marked deprecated.
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

  # You shouldn't mix sync and async code, and TestMetadata.put() invokes a
  # complex _pre_put_hook() that will take a lot of work to get rid of. For
  # now we simply queue up a separate task to do the actual creation of
  # stoppage alerts or test deprecation. This happens infrequently anyway, the
  # much more common case is nothing happens.
  if not last_row:
    should_deprecate = yield _CheckSuiteShouldBeDeprecated(entity)
    if should_deprecate:
      _AddDeprecateTestDataTask({
          'type': 'deprecate-test',
          'test_key': entity.key.urlsafe()})
    return

  if last_row.timestamp < now - _DEPRECATION_REVISION_DELTA:
    _AddDeprecateTestDataTask({
        'type': 'deprecate-test',
        'test_key': entity.key.urlsafe()})

  should_create_alert = yield _ShouldCreateStoppageAlerts(entity, last_row)
  if should_create_alert:
    _AddDeprecateTestDataTask({
        'type': 'create-stoppage-alert',
        'row_key': last_row.key.urlsafe(),
        'test_key': entity.key.urlsafe()})


def _IsRef(test):
  if test.test_path.endswith('/ref') or test.test_path.endswith('_ref'):
    return True
  return False


def _AddDeprecateTestDataTask(params):
  taskqueue.add(
      url='/deprecate_tests',
      params=params,
      queue_name=_DEPRECATE_TESTS_TASK_QUEUE_NAME)


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
def _ShouldCreateStoppageAlerts(test, last_row):
  """Checks to see if we should create a StoppageAlert for the test."""
  if not test.sheriff or _IsRef(test):
    raise ndb.Return(False)
  sheriff_entity = yield test.sheriff.get_async()
  warn_sheriff_delay_days = sheriff_entity.stoppage_alert_delay
  if warn_sheriff_delay_days < 0:
    raise ndb.Return(False)
  now = datetime.datetime.now()
  warn_sheriff_delta = datetime.timedelta(days=warn_sheriff_delay_days)
  earliest_warn_time = now - warn_sheriff_delta
  if last_row.timestamp >= earliest_warn_time:
    raise ndb.Return(False)
  existing_stoppage_alert = yield stoppage_alert.GetStoppageAlertAsync(
      test.test_path, last_row.revision)
  if existing_stoppage_alert:
    raise ndb.Return(False)
  raise ndb.Return(True)


def _CreateStoppageAlerts(test_key, last_row_key):
  """Creates a StoppageAlert for the test.

  A stoppage alert is an alert created to warn people that data has not
  been received for a particular test for some length of time. An alert
  will only be created if the stoppage_alert_delay property of the sheriff
  is non-zero -- the value of this property is the number of days that should
  pass before an alert is created.

  Args:
    test_key: A TestMetadata entity key.
    last_row_key: The Row entity key that was last added.
  Return:
    True, if we should create a stoppage alert, False otherwise.
  """
  test = test_key.get()
  last_row = last_row_key.get()

  new_alert = stoppage_alert.CreateStoppageAlert(test, last_row)
  if not new_alert:
    return
  new_alert.put()


def _MarkTestDeprecated(test_key):
  """Marks a TestMetadata as deprecated and clears any related cached data."""
  logging.info("_MarkTestDeprecated: %s", str(test_key.id()))
  test = test_key.get()
  test.deprecated = True
  test.put()
  _DeleteCachedTestData(test)


def _DeleteCachedTestData(test):
  # The sub-test listing function returns different results depending
  # on whether tests are deprecated, so when a new suite is deprecated,
  # the cache needs to be cleared.
  return layered_cache.DeleteAsync(graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
      test.master_name, test.bot_name, test.suite_name))


@ndb.tasklet
def _CheckSuiteShouldBeDeprecated(suite):
  """Checks if a suite should be deprecated."""
  # If this is a suite, check if we can deprecate the entire suite
  if len(suite.key.id().split('/')) == 3:
    # Check whether the test suite now contains only deprecated tests, and
    # if so, deprecate it too.
    all_deprecated = yield _AllSubtestsDeprecated(suite)
    if all_deprecated:
      raise ndb.Return(True)
  raise ndb.Return(False)


@ndb.tasklet
def _AllSubtestsDeprecated(test):
  descendant_tests = yield list_tests.GetTestDescendantsAsync(
      test.key, has_rows=True, keys_only=False)
  result = all(t.deprecated for t in descendant_tests)
  raise ndb.Return(result)
