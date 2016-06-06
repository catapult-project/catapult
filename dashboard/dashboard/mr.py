# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Mapper functions for mapreduce jobs.

Jobs can also be started through the /mapreduce endpoint. Configuration
for jobs started through that endpoint is set in mapreduce.yaml.

See:
  https://code.google.com/p/appengine-mapreduce/wiki/GettingStartedInPython

Note about running mapreduce jobs that write to the datastore while datastore
writes are disabled: There is a parameter 'force_ops_writes' for mapreduce jobs
that is supposed to force writes. Another way of forcing writes for a one-off
job is to deploy a version of the app with the force writes option always set to
True the mapreduce code (see mapreduce/util.py line 334).
"""

import datetime
import logging

from mapreduce import control as mr_control
from mapreduce import operation as op

from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import layered_cache
from dashboard import list_tests
from dashboard import request_handler
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import stoppage_alert

# Length of time required to pass for a test to be considered deprecated.
_OLDEST_REVISION_DELTA = datetime.timedelta(days=14)

# The time between runs of the deprecate test job.
# This should be kept in sync with the time interval in cron.yaml.
_DEPRECATE_JOB_INTERVAL = datetime.timedelta(days=2)


def SaveAllMapper(entity):
  """This mapper just puts an entity.

  When an entity is put, the pre-put hook is called, which may update some
  property of the entity.

  This may also be needed after adding a new index on an existing property,
  or adding a query for a new property with a default value.

  Args:
    entity: The entity to put. Can be any kind.
  """
  entity.put()


class MRDeprecateTestsHandler(request_handler.RequestHandler):
  """Handler to run a deprecate tests mapper job."""

  def get(self):
    # TODO(qyearsley): Add test coverage. See catapult:#1346.
    name = 'Update test deprecation status.'
    handler = ('dashboard.mr.DeprecateTestsMapper')
    reader = 'mapreduce.input_readers.DatastoreInputReader'
    mapper_parameters = {
        'entity_kind': ('dashboard.models.graph_data.TestMetadata'),
        'filters': [('has_rows', '=', True),
                    ('deprecated', '=', False)],
    }
    mr_control.start_map(name, handler, reader, mapper_parameters)


def DeprecateTestsMapper(entity):
  """Marks a TestMetadata entity as deprecated if the last row is too old.

  What is considered "too old" is defined by _OLDEST_REVISION_DELTA. Also,
  if all of the subtests in a test have been marked as deprecated, then that
  parent test will be marked as deprecated.

  This mapper doesn't un-deprecate tests if new data has been added; that
  happens in add_point.py.

  Args:
    entity: The TestMetadata entity to check.

  Yields:
    Zero or more datastore mutation operations.
  """
  # Make sure that we have a non-deprecated TestMetadata with Rows.
  if (entity.key.kind() != 'TestMetadata' or
      not entity.has_rows or
      entity.deprecated):
    # TODO(qyearsley): Add test coverage. See catapult:#1346.
    logging.error(
        'Got bad entity in mapreduce! Kind: %s, has_rows: %s, deprecated: %s',
        entity.key.kind(), entity.has_rows, entity.deprecated)
    return

  # Fetch the last row.
  datastore_hooks.SetPrivilegedRequest()
  query = graph_data.Row.query(
      graph_data.Row.parent_test == utils.OldStyleTestKey(entity.key))
  query = query.order(-graph_data.Row.timestamp)
  last_row = query.get()
  if not last_row:
    # TODO(qyearsley): Add test coverage. See catapult:#1346.
    logging.error('No rows for %s (but has_rows=True)', entity.key)
    return

  now = datetime.datetime.now()
  if last_row.timestamp < now - _OLDEST_REVISION_DELTA:
    for operation in _MarkDeprecated(entity):
      yield operation

  for operation in _CreateStoppageAlerts(entity, last_row):
    yield operation


def _CreateStoppageAlerts(test, last_row):
  """Yields put operations for any StoppageAlert that may be created.

  A stoppage alert is an alert created to warn people that data has not
  been received for a particular test for some length of time. An alert
  will only be created if the stoppage_alert_delay property of the sheriff
  is non-zero -- the value of this property is the number of days that should
  pass before an alert is created.

  Args:
    test: A TestMetadata entity.
    last_row: The Row entity that was last added.

  Yields:
    Either one op.db.Put, or nothing.
  """
  if not test.sheriff:
    return
  sheriff_entity = test.sheriff.get()
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
  yield op.db.Put(new_alert)


def _MarkDeprecated(test):
  """Marks a TestMetadata as deprecated and yields Put operations."""
  test.deprecated = True
  yield op.db.Put(test)

  # The sub-test listing function returns different results depending
  # on whether tests are deprecated, so when a new suite is deprecated,
  # the cache needs to be cleared.
  layered_cache.Delete(graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
      test.master_name, test.bot_name, test.suite_name))

  # Check whether the test suite now contains only deprecated tests, and
  # if so, deprecate it too.
  suite = ndb.Key(
      'TestMetadata', '%s/%s/%s' % (
          test.master_name, test.bot_name, test.suite_name)).get()
  if suite and not suite.deprecated and _AllSubtestsDeprecated(suite):
    suite.deprecated = True
    yield op.db.Put(suite)


def _AllSubtestsDeprecated(test):
  """Checks whether all descendant tests are marked as deprecated."""
  descendant_tests = list_tests.GetTestDescendants(
      test.key, has_rows=True, keys_only=False)
  return all(t.deprecated for t in descendant_tests)
