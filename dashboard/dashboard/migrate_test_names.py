# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue task which migrates a TestMetadata and its Rows to a new name.

A rename consists of listing all TestMetadata entities which match the old_name,
and then, for each, completing these steps:
  * Create a new TestMetadata entity with the new name.
  * Re-parent all TestMetadata and Row entities from the old TestMetadata to
  * the new TestMetadata.
  * Update alerts to reference the new TestMetadata.
  * Delete the old TestMetadata.

For any rename, there could be hundreds of TestMetadatas and many thousands of
Rows. Datastore operations often time out after a few hundred puts(), so this
task is split up using the task queue.
"""

import re

from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import graph_revisions
from dashboard import list_tests
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data

_MAX_DATASTORE_PUTS_PER_PUT_MULTI_CALL = 50

# Properties of TestMetadata that should not be copied when a TestMetadata is
# being copied.
_TEST_COMPUTED_PROPERTIES = [
    'bot',
    'parent_test',
    'test_path',
    'id',
    'master_name',
    'bot_name',
    'suite_name',
    'test_part1_name',
    'test_part2_name',
    'test_part3_name',
    'test_part4_name',
    'test_part5_name',
]
# The following shouldn't be copied because they were removed from the Model;
# Creating a new entity with one of these properties will result in an error.
_TEST_DEPRECATED_PROPERTIES = [
    'has_multi_value_rows',
    'important',
    'is_stacked',
    'last_added_revision',
    'overridden_gasp_modelset',
    'units_x',
    'buildername',
    'masterid',
    'stoppage_alert'
]
_TEST_EXCLUDE = _TEST_COMPUTED_PROPERTIES + _TEST_DEPRECATED_PROPERTIES

# Properties of Row that shouldn't be copied.
_ROW_EXCLUDE = ['parent_test', 'revision', 'id']

_SHERIFF_ALERT_EMAIL_BODY = """
The test %(old_test_path)s has been migrated to %(new_test_path)s.

It was previously sheriffed by %(old_sheriff)s.

Please ensure the new test is properly sheriffed!
"""

# Match square brackets and group inside them.
_BRACKETS_REGEX = r'\[([^\]]*)\]'

# Queue name needs to be listed in queue.yaml.
_TASK_QUEUE_NAME = 'migrate-test-names-queue'


class BadInputPatternError(Exception):
  pass


class MigrateTestNamesHandler(request_handler.RequestHandler):
  """Migrates the data for a test which has been renamed on the buildbots."""

  def get(self):
    """Displays a simple UI form to kick off migrations."""
    self.RenderHtml('migrate_test_names.html', {})

  def post(self):
    """Starts migration of old TestMetadata entity names to new ones.

    The form that's used to kick off migrations will give the parameters
    old_pattern and new_pattern, which are both test path pattern strings.

    When this handler is called from the task queue, however, it will be given
    the parameters old_test_key and new_test_key, which should both be keys
    of TestMetadata entities in urlsafe form.
    """
    datastore_hooks.SetPrivilegedRequest()

    old_pattern = self.request.get('old_pattern')
    new_pattern = self.request.get('new_pattern')
    kicked_off = self.request.get('kicked_off')
    old_test_key = self.request.get('old_test_key')
    new_test_key = self.request.get('new_test_key')

    if old_pattern and new_pattern:
      if not kicked_off:
        try:
          _AddKickoffTask(old_pattern, new_pattern)
          self.RenderHtml('result.html', {
              'headline': 'Test name migration task started.'
          })
        except BadInputPatternError as error:
          self.ReportError('Error: %s' % error.message, status=400)
      else:
        _AddTasksForPattern(old_pattern, new_pattern)
    elif old_test_key and new_test_key:
      _MigrateOldTest(old_test_key, new_test_key)
    else:
      self.ReportError('Missing required parameters of /migrate_test_names.')


def _AddKickoffTask(old_pattern, new_pattern):
  _ValidateTestPatterns(old_pattern, new_pattern)

  task_params = {
      'old_pattern': old_pattern,
      'new_pattern': new_pattern,
      'kicked_off': '1',
  }
  taskqueue.add(
      url='/migrate_test_names',
      params=task_params,
      queue_name=_TASK_QUEUE_NAME)


def _ValidateTestPatterns(old_pattern, new_pattern):
  tests = list_tests.GetTestsMatchingPattern(old_pattern, list_entities=True)
  for test in tests:
    old_path = utils.TestPath(test.key)
    _ValidateAndGetNewTestPath(old_path, new_pattern)


def _AddTasksForPattern(old_pattern, new_pattern):
  """Enumerates individual test migration tasks and enqueues them.

  Typically, this function is called by a request initiated by the user.
  The purpose of this function is to queue up a set of requests which will
  do all of the actual work.

  Args:
    old_pattern: Test path pattern for old names.
    new_pattern: Test path pattern for new names.

  Raises:
    BadInputPatternError: Something was wrong with the input patterns.
  """
  tests = list_tests.GetTestsMatchingPattern(old_pattern, list_entities=True)
  for test in tests:
    _AddTaskForTest(test, new_pattern)


def _AddTaskForTest(test, new_pattern):
  """Adds a task to the task queue to migrate a TestMetadata entity
     and its descendants.

  Args:
    test: A TestMetadata entity.
    new_pattern: A test path pattern which determines the new name.
  """
  old_path = utils.TestPath(test.key)
  new_path = _ValidateAndGetNewTestPath(old_path, new_pattern)

  # Copy the new test from the old test. The new parent should exist.
  new_test_key = _CreateRenamedEntityIfNotExists(
      graph_data.TestMetadata, test, new_path, None, _TEST_EXCLUDE).put()
  task_params = {
      'old_test_key': test.key.urlsafe(),
      'new_test_key': new_test_key.urlsafe(),
  }
  taskqueue.add(
      url='/migrate_test_names',
      params=task_params,
      queue_name=_TASK_QUEUE_NAME)


def _ValidateAndGetNewTestPath(old_path, new_pattern):
  """Returns the destination test path that a test should be renamed to.

  The given |new_pattern| consists of a sequence of parts separated by slashes,
  and each part can be one of:
   (1) a single asterisk; in this case the corresponding part of the original
       test path will be used.
   (2) a string with brackets; which means that the corresponding part of the
       original test path should be used, but with the bracketed part removed.
   (3) a literal string; in this case this literal string will be used.

  The new_pattern can have fewer parts than the old test path; it can also be
  longer, but in this case the new pattern can't contain asterisks or brackets
  in the parts at the end.

  Args:
    old_path: A test path, e.g. ChromiumPerf/linux/sunspider/Total
    new_pattern: A destination path pattern.

  Returns:
    The new test path to use.

  Raises:
    BadInputPatternError: Something was wrong with the input patterns.
  """
  assert '*' not in old_path, '* should never appear in actual test paths.'
  old_path_parts = old_path.split('/')
  new_pattern_parts = new_pattern.split('/')
  new_path_parts = []
  for old_part, new_part in map(None, old_path_parts, new_pattern_parts):
    if not new_part:
      break  # In this case, the new path is shorter than the old.
    elif new_part == '*':
      # The old part field must exist.
      if not old_part:
        raise BadInputPatternError('* in new pattern has no corresponding '
                                   'part in old test path %s' % old_path)
      new_path_parts.append(old_part)
    elif re.search(_BRACKETS_REGEX, new_part):
      # A string contained in brackets in new path should be replaced by
      # old path with that string deleted. If the current part of old_path
      # is exactly that string, the new path rows are parented to the
      # previous part of old path.
      modified_old_part = _RemoveBracketedSubstring(old_part, new_part)
      if not modified_old_part:
        break
      new_path_parts.append(modified_old_part)
    else:
      if '*' in new_part:
        raise BadInputPatternError('Unexpected * in new test path pattern.')
      new_path_parts.append(new_part)
  return '/'.join(new_path_parts)


def _RemoveBracketedSubstring(old_part, new_part):
  """Returns the new name obtained by removing the given substring.

  Examples:
    _RemoveBracketedSubstring('asdf', '[sd]') => 'af'
    _RemoveBracketedSubstring('asdf', '[asdf]') => ''
    _RemoveBracketedSubstring('asdf', '[xy]') => Exception

  Args:
    old_part: A part of a test path.
    new_part: A string starting and ending with brackets, where the part
        inside the brackets is a substring of |old_part|.

  Returns:
    The |old_part| string with the substring removed.

  Raises:
    BadInputPatternError: The input was invalid.
  """
  substring_to_remove = re.search(_BRACKETS_REGEX, new_part).group(1)
  if substring_to_remove not in old_part:
    raise BadInputPatternError('Bracketed part not in %s.' % old_part)
  modified_old_part = old_part.replace(substring_to_remove, '', 1)
  return modified_old_part


def _MigrateOldTest(old_test_key_urlsafe, new_test_key_urlsafe):
  """Migrates Rows for one test.

  This migrates up to _MAX_DATASTORE_PUTS_PER_PUT_MULTI_CALL Rows at once
  for one level of descendant tests of old_test_key. Adds tasks to the task
  queue so that it will be called again until there is nothing to migrate.

  Args:
    old_test_key_urlsafe: Key of old TestMetadata entity in urlsafe form.
    new_test_key_urlsafe: Key of new TestMetadata entity in urlsafe form.
  """
  old_test_key = ndb.Key(urlsafe=old_test_key_urlsafe)
  new_test_key = ndb.Key(urlsafe=new_test_key_urlsafe)
  finished = _MigrateTestToNewKey(old_test_key, new_test_key)
  if not finished:
    task_params = {
        'old_test_key': old_test_key_urlsafe,
        'new_test_key': new_test_key_urlsafe,
    }
    taskqueue.add(
        url='/migrate_test_names',
        params=task_params,
        queue_name=_TASK_QUEUE_NAME)


def _MigrateTestToNewKey(old_test_key, new_test_key):
  """Migrates data (Row entities) from the old to the new test.

  Migrating all rows in one request is usually too much work to do before
  we hit a deadline exceeded error, so this function only does a limited
  chunk of work at one time.

  Args:
    old_test_key: The key of the TestMetadata to migrate data from.
    new_test_key: The key of the TestMetadata to migrate data to.

  Returns:
    True if finished or False if there is more work.
  """
  futures = []

  # Try to re-parent children test first. If this does not complete in one
  # request, the reset of the actions should be done in a separate request.
  if not _ReparentChildTests(old_test_key, new_test_key):
    return False

  migrate_rows_result = _MigrateTestRows(old_test_key, new_test_key)
  if migrate_rows_result['moved_rows']:
    futures += migrate_rows_result['put_future']
    futures += migrate_rows_result['delete_future']
    ndb.Future.wait_all(futures)
    return False

  futures += _MigrateAnomalies(old_test_key, new_test_key)

  if not futures:
    _SendNotificationEmail(old_test_key, new_test_key)
    old_test_key.delete()
  else:
    ndb.Future.wait_all(futures)
    return False

  return True


def _ReparentChildTests(old_parent_key, new_parent_key):
  """Migrates child tests from one parent test to another.

  This will involve calling |_MigrateTestToNewKey|, which then
  recursively moves children under these children until all of
  the children are moved.

  Args:
    old_parent_key: TestMetadata entity key of the test to move from.
    new_parent_key: TestMetadata entity key of the test to move to.

  Returns:
    True if finished, False otherwise.
  """
  tests_to_reparent = graph_data.TestMetadata.query(
      graph_data.TestMetadata.parent_test == old_parent_key).fetch(
          limit=_MAX_DATASTORE_PUTS_PER_PUT_MULTI_CALL)
  for test in tests_to_reparent:
    new_test_path = '%s/%s' % (utils.TestPath(new_parent_key), test.test_name)
    new_subtest_key = _CreateRenamedEntityIfNotExists(
        graph_data.TestMetadata, test, new_test_path, None, _TEST_EXCLUDE).put()
    finished = _MigrateTestToNewKey(test.key, new_subtest_key)
    if not finished:
      return False
  return True


def _MigrateTestRows(old_parent_key, new_parent_key):
  """Copies Row entities from one parent to another, deleting old ones.

  Args:
    old_parent_key: TestMetadata entity key of the test to move from.
    new_parent_key: TestMetadata entity key of the test to move to.

  Returns:
    A dictionary with the following keys:
      put_future: A list of Future objects for entities being put.
      delete_future: A list of Future objects for entities being deleted.
      moved_rows: Whether or not any entities were moved.
  """
  # In this function we'll build up lists of entities to put and delete
  # before returning Future objects for the entities being put and deleted.
  rows_to_put = []
  rows_to_delete = []

  # Add some Row entities to the lists of entities to put and delete.
  rows = graph_data.GetLatestRowsForTest(
      old_parent_key, _MAX_DATASTORE_PUTS_PER_PUT_MULTI_CALL)
  for row in rows:
    rows_to_put.append(_CreateRenamedEntityIfNotExists(
        graph_data.Row, row, row.key.id(), new_parent_key, _ROW_EXCLUDE))
    rows_to_delete.append(row.key)

  # Clear the cached revision range selector data for both the old and new
  # tests because it will no longer be valid after migration. The cache should
  # be updated with accurate data the next time it's set, which will happen
  # when someone views the graph.
  graph_revisions.DeleteCache(utils.TestPath(old_parent_key))
  graph_revisions.DeleteCache(utils.TestPath(new_parent_key))

  return {
      'put_future': ndb.put_multi_async(rows_to_put),
      'delete_future': ndb.delete_multi_async(rows_to_delete),
      'moved_rows': bool(rows_to_put),
  }


def _MigrateAnomalies(old_parent_key, new_parent_key):
  """Copies the Anomaly entities from one test to another.

  Args:
    old_parent_key: Source TestMetadata entity key.
    new_parent_key: Destination TestMetadata entity key.

  Returns:
    A list of Future objects for Anomaly entities to update.
  """
  anomalies_to_update = anomaly.Anomaly.GetAlertsForTest(
      old_parent_key, limit=_MAX_DATASTORE_PUTS_PER_PUT_MULTI_CALL)
  if not anomalies_to_update:
    return []
  for anomaly_entity in anomalies_to_update:
    anomaly_entity.test = new_parent_key
  return ndb.put_multi_async(anomalies_to_update)


def _SendNotificationEmail(old_test_key, new_test_key):
  """Send a notification email about the test migration.

  This function should be called after we have already found out that there are
  no new rows to move from the old test to the new test, but before we actually
  delete the old test.

  Args:
    old_test_key: TestMetadata key of the test that's about to be deleted.
    new_test_key: TestMetadata key of the test that's replacing the old one.
  """
  old_entity = old_test_key.get()
  if not old_entity or not old_entity.sheriff:
    return
  body = _SHERIFF_ALERT_EMAIL_BODY % {
      'old_test_path': utils.TestPath(old_test_key),
      'new_test_path': utils.TestPath(new_test_key),
      'old_sheriff': old_entity.sheriff.string_id(),
  }
  mail.send_mail(sender='gasper-alerts@google.com',
                 to='chrome-performance-monitoring-alerts@google.com',
                 subject='Sheriffed Test Migrated',
                 body=body)


def _CreateRenamedEntityIfNotExists(
    cls, old_entity, new_name, parent_key, exclude):
  """Create an entity with the desired name if one does not exist.

  Args:
    cls: The class of the entity to create, either Row or TestMetadata.
    old_entity: The old entity to copy.
    new_name: The string id of the new entity.
    parent_key: The ndb.Key for the parent test of the new entity.
    exclude: Properties to not copy from the old entity.

  Returns:
    The new Row or TestMetadata entity (or the existing one).
  """
  new_entity = cls.get_by_id(new_name, parent=parent_key)
  if new_entity:
    return new_entity
  if old_entity.key.kind() == 'Row':
    parent_key = utils.GetTestContainerKey(parent_key)
  create_args = {
      'id': new_name,
      'parent': parent_key,
  }
  for prop, val in old_entity.to_dict(exclude=exclude).iteritems():
    create_args[prop] = val
  new_entity = cls(**create_args)
  return new_entity
