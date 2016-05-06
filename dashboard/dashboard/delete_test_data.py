# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Task queue task which deletes a Test, its subtest, and all their Rows.

A delete consists of listing all Test entities which match the name pattern,
and then, for each, recursively deleting all child Row entities and then Tests.

For any delete, there could be hundreds of Tests and many thousands of Rows.
Datastore operations often time out after a few hundred deletes(), so this task
is split up using the task queue.
"""

from google.appengine.api import mail
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import list_tests
from dashboard import request_handler
from dashboard import utils
from dashboard.models import graph_data

_ROWS_TO_DELETE_AT_ONCE = 500
_MAX_DELETIONS_PER_TASK = 30

_SHERIFF_ALERT_EMAIL_BODY = """
The test %(test_path)s has been DELETED.

It was previously sheriffed by %(sheriff)s.

Please ensure this is intended!
"""

# Queue name needs to be listed in queue.yaml.
_TASK_QUEUE_NAME = 'delete-tests-queue'


class BadInputPatternError(Exception):
  pass


class DeleteTestDataHandler(request_handler.RequestHandler):
  """Deletes the data for a test."""

  def get(self):
    """Displays a simple UI form to kick off migrations."""
    self.RenderHtml('delete_test_data.html', {})

  def post(self):
    """Recursively deletes Test and Row data.

    The form that's used to kick off migrations will give the parameter
    pattern, which is a test path pattern string.

    When this handler is called from the task queue, however, it will be given
    the parameter test_key, which should be a key of a Test entity in urlsafe
    form.
    """
    datastore_hooks.SetPrivilegedRequest()

    pattern = self.request.get('pattern')
    test_key = self.request.get('test_key')

    if pattern:
      try:
        _AddTasksForPattern(pattern)
        self.RenderHtml('result.html', {
            'headline': 'Test deletion task started.'
        })
      except BadInputPatternError as error:
        self.ReportError('Error: %s' % error.message, status=400)
    elif test_key:
      _DeleteTest(test_key)
    else:
      self.ReportError('Missing required parameters of /delete_test_data.')


def _AddTasksForPattern(pattern):
  """Enumerates individual test deletion tasks and enqueues them.

  Typically, this function is called by a request initiated by the user.
  The purpose of this function is to queue up a set of requests which will
  do all of the actual work.

  Args:
    pattern: Test path pattern for Tests to delete.

  Raises:
    BadInputPatternError: Something was wrong with the input pattern.
  """
  tests = list_tests.GetTestsMatchingPattern(pattern, list_entities=True)
  for test in tests:
    _AddTaskForTest(test)


def _AddTaskForTest(test):
  """Adds a task to the task queue to delete a Test and its descendants.

  Args:
    test: A Test entity.
  """
  task_params = {
      'test_key': test.key.urlsafe(),
  }
  taskqueue.add(
      url='/delete_test_data',
      params=task_params,
      queue_name=_TASK_QUEUE_NAME)


def _DeleteTest(test_key_urlsafe):
  """Deletes data for one Test.

  This gets all the descendant Test entities, and deletes their Row entities,
  then when the Row entities are all deleted, deletes the Test. This is often
  too much work to do in a single task, so if it doesn't finish, it will
  re-add itself to the same task queue and retry.
  """
  test_key = ndb.Key(urlsafe=test_key_urlsafe)
  finished = _DeleteTestData(test_key)
  if not finished:
    task_params = {
        'test_key': test_key_urlsafe,
    }
    taskqueue.add(
        url='/delete_test_data',
        params=task_params,
        queue_name=_TASK_QUEUE_NAME)


def _DeleteTestData(test_key):
  futures = []
  num_tests_processed = 0
  finished = True
  descendants = graph_data.Test.query(ancestor=test_key).fetch(keys_only=True)
  descendants.append(test_key)
  for descendant in descendants:
    rows = graph_data.Row.query(graph_data.Row.parent_test == descendant).fetch(
        keys_only=True, limit=_ROWS_TO_DELETE_AT_ONCE)
    if rows:
      futures.extend(ndb.delete_multi_async(rows))
      finished = False
      num_tests_processed += 1
      if num_tests_processed > _MAX_DELETIONS_PER_TASK:
        break

  # Only delete Test entities after all Row entities have been deleted.
  if finished:
    descendants = ndb.get_multi(descendants)
    for descendant in descendants:
      _SendNotificationEmail(descendant)
      futures.append(descendant.key.delete_async())


  ndb.Future.wait_all(futures)
  return finished


def _SendNotificationEmail(test):
  """Send a notification email about the test deletion.

  Args:
    test_key: Test key of the test that's about to be deleted.
  """
  if not test or not test.sheriff:
    return
  body = _SHERIFF_ALERT_EMAIL_BODY % {
      'test_path': utils.TestPath(test.key),
      'sheriff': test.sheriff.string_id(),
  }
  mail.send_mail(sender='gasper-alerts@google.com',
                 to='chrome-performance-monitoring-alerts@google.com',
                 subject='Sheriffed Test Deleted',
                 body=body)
