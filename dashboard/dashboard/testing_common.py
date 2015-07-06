# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions used in multiple unit tests."""

import base64
import json
import os
import re
import unittest
import urllib

from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard import utils
from dashboard.models import graph_data


class TestCase(unittest.TestCase):
  """Common base class for test cases."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_mail_stub()
    self.mail_stub = self.testbed.get_stub(testbed.MAIL_SERVICE_NAME)
    self.testbed.init_memcache_stub()
    self.testbed.init_taskqueue_stub(root_path=os.path.dirname(__file__))
    self.testbed.init_user_stub()
    self.testbed.init_urlfetch_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def ExecuteTaskQueueTasks(self, handler_name, task_queue_name):
    """Executes all of the tasks on the queue until there are none left."""
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks(task_queue_name)
    taskq.FlushQueue(task_queue_name)
    for task in tasks:
      self.testapp.post(handler_name,
                        urllib.unquote_plus(base64.b64decode(task['body'])))
      self.ExecuteTaskQueueTasks(handler_name, task_queue_name)

  def ExecuteDeferredTasks(self, task_queue_name):
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks(task_queue_name)
    taskq.FlushQueue(task_queue_name)
    for task in tasks:
      deferred.run(base64.b64decode(task['body']))
      self.ExecuteDeferredTasks(task_queue_name)

  def SetCurrentUser(self, email, user_id='123456', is_admin=False):
    """Sets the user in the environment in the current testbed."""
    email = email or ''
    user_id = user_id or ''
    is_admin = '1' if is_admin else '0'
    self.testbed.setup_env(user_is_admin=is_admin,
                           user_email=email,
                           user_id=user_id,
                           overwrite=True)


def AddDataToMockDataStore(masters, bots, tests_dict):
  """Adds data to the mock datastore.

  Args:
    masters: List of buildbot master names.
    bots: List of bot names.
    tests_dict: Nested dictionary of tests to add; keys are test names
        and values are nested dictionaries of tests to add.
  """
  for master_name in masters:
    master_key = graph_data.Master(id=master_name).put()
    for bot_name in bots:
      bot_key = graph_data.Bot(id=bot_name, parent=master_key).put()
      for test_name in tests_dict:
        test_key = graph_data.Test(id=test_name, parent=bot_key).put()
        _AddMockSubTestToDataStore(test_key, tests_dict[test_name])


def _AddMockSubTestToDataStore(parent_test_key, subtests_dict):
  """Helper function to recursively add sub-Tests to a Test.

  Args:
    parent_test_key: A Test key.
    subtests_dict: A dict of test names to dictionaries of subtests.
  """
  for test_name in subtests_dict:
    test_key = graph_data.Test(id=test_name, parent=parent_test_key).put()
    _AddMockSubTestToDataStore(test_key, subtests_dict[test_name])


def AddRows(test_path, row_dicts):
  """Adds Rows to a given test.

  Args:
    test_path: Full test path of Test entity to add Rows to.
    row_dicts: List of dictionaries, each of which contains properties for
        one Row entity.
  """
  test_key = utils.TestKey(test_path)
  test_container_key = utils.GetTestContainerKey(test_key)
  rows_to_put = []
  for index, row_dict in enumerate(row_dicts):
    # Note, index 0 is invalid for a datastore entity.
    int_id = index + 1
    # Use id or revision if given.
    if 'id' in row_dict:
      int_id = row_dict.pop('id')
    if 'revision' in row_dict:
      int_id = row_dict.pop('revision')
    row = graph_data.Row(id=int_id, parent=test_container_key, **row_dict)
    rows_to_put.append(row)
  ndb.put_multi(rows_to_put)


def GetEmbeddedVariable(response, var_name):
  """Gets a variable embedded in a script element in a response.

  Args:
    response: A webtest.TestResponse object.
    var_name: The name of the variable to fetch the value of.

  Returns:
    A value obtained from de-JSON-ifying the embedded variable,
    or None if no such value could be found in the response.
  """
  scripts_elements = response.html('script')
  for script_element in scripts_elements:
    contents = script_element.renderContents()
    # Assume that the variable is all one line, with no line breaks.
    match = re.search(var_name + r'\s+=\s+([^\;]*)', contents)
    if match:
      javascript_value = match.group(1)
      return json.loads(javascript_value)
  return None


class FakeResponseObject(object):
  """Fake Response Object which can be returned by urlfetch mocks."""

  def __init__(self, status_code, content):
    self.status_code = status_code
    self.content = content
