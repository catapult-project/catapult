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

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import layered_cache
from dashboard import list_tests
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import graph_data

# Length of time required to pass for a test to be considered deprecated.
_DEPRECATION_REVISION_DELTA = datetime.timedelta(days=14)

# Length of time required to pass for a test to be deleted entirely.
_REMOVAL_REVISON_DELTA = datetime.timedelta(days=183)

# The time between runs of the deprecate test job.
# This should be kept in sync with the time interval in cron.yaml.
_DEPRECATE_JOB_INTERVAL = datetime.timedelta(days=2)

_DELETE_TASK_QUEUE_NAME = 'delete-tests-queue'


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


class MRStoreUnitsHandler(request_handler.RequestHandler):
  """Handler to run a anomaly units mapper job."""

  def get(self):
    name = 'Update anomalies with units.'
    handler = ('dashboard.mr.StoreUnitsInAnomalyEntity')
    reader = 'mapreduce.input_readers.DatastoreInputReader'
    mapper_parameters = {
        'entity_kind': ('dashboard.models.graph_data.Anomaly'),
        'filters': [],
    }
    mr_control.start_map(name, handler, reader, mapper_parameters)

def StoreUnitsInAnomalyEntity(entity):
  """Puts units field from the TestMetaData entity into the anomaly directly.

  We would like to store the units in the anomaly directly, for speedier
  lookup.

  Args:
    anomaly: The Anomaly entity to check.

  Yields:
    One datastore mutation operation.
  """
  if entity.test:
    test_key = utils.TestMetadataKey(entity.test)
    test = test_key.get()
    if test:
      entity.units = test.units
  yield op.db.Put(entity)


class MRDeprecateTestsHandler(request_handler.RequestHandler):
  """Handler to run a deprecate tests mapper job."""

  def get(self):
    name = 'Update test deprecation status.'
    handler = ('dashboard.mr.DeprecateTestsMapper')
    reader = 'mapreduce.input_readers.DatastoreInputReader'
    mapper_parameters = {
        'entity_kind': ('dashboard.models.graph_data.TestMetadata'),
        'filters': [],
    }
    mr_control.start_map(name, handler, reader, mapper_parameters)


def DeprecateTestsMapper(entity):
  """Marks a TestMetadata entity as deprecated if the last row is too old.

  What is considered "too old" is defined by _DEPRECATION_REVISION_DELTA. Also,
  if all of the subtests in a test have been marked as deprecated, then that
  parent test will be marked as deprecated.

  This mapper doesn't un-deprecate tests if new data has been added; that
  happens in add_point.py.

  Args:
    entity: The TestMetadata entity to check.

  Yields:
    Zero or more datastore mutation operations.
  """
  # Fetch the last row.
  datastore_hooks.SetPrivilegedRequest()
  query = graph_data.Row.query(
      graph_data.Row.parent_test == utils.OldStyleTestKey(entity.key))
  query = query.order(-graph_data.Row.timestamp)
  last_row = query.get()

  # Check if the test should be deleted entirely.
  now = datetime.datetime.now()
  logging.info('checking %s', entity.test_path)
  if not last_row or last_row.timestamp < now - _REMOVAL_REVISON_DELTA:
    descendants = list_tests.GetTestDescendants(entity.key, keys_only=True)
    if entity.key in descendants:
      descendants.remove(entity.key)
    if not descendants:
      logging.info('removing')
      if last_row:
        logging.info('last row timestamp: %s', last_row.timestamp)
      else:
        logging.info('no last row, no descendants')
      taskqueue.add(
          url='/delete_test_data',
          params={
              'test_path': utils.TestPath(entity.key),  # For manual inspection.
              'test_key': entity.key.urlsafe(),
              'notify': 'false',
          },
          queue_name=_DELETE_TASK_QUEUE_NAME)
      return


  if entity.deprecated or not last_row:
    return

  if last_row.timestamp < now - _DEPRECATION_REVISION_DELTA:
    for operation in _MarkDeprecated(entity):
      yield operation


def _IsRef(test):
  if test.test_path.endswith('/ref') or test.test_path.endswith('_ref'):
    return True

  return False


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
