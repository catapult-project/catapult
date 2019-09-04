# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions used in multiple unit tests."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import json
import logging
import mock
import os
import re
import sys
import unittest
import urllib
import webapp2
import webtest

from google.appengine.api import oauth
from google.appengine.api import users
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.common import datastore_hooks
from dashboard.common import stored_object
from dashboard.common import utils
from dashboard.models import graph_data

_QUEUE_YAML_DIR = os.path.join(os.path.dirname(__file__), '..', '..')

SERVICE_ACCOUNT_USER = users.User(
    email='fake@foo.gserviceaccount.com', _auth_domain='google.com')
INTERNAL_USER = users.User(
    email='internal@example.com', _auth_domain='google.com')
EXTERNAL_USER = users.User(
    email='external@example.com', _auth_domain='example.com')


class FakeRequestObject(object):
  """Fake Request object which can be used by datastore_hooks mocks."""

  def __init__(self, remote_addr=None):
    self.registry = {}
    self.remote_addr = remote_addr


class FakeResponseObject(object):
  """Fake Response Object which can be returned by urlfetch mocks."""

  def __init__(self, status_code, content):
    self.status_code = status_code
    self.content = content


class TestCase(unittest.TestCase):
  """Common base class for test cases."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.addCleanup(self.testbed.deactivate)

    self.testbed.init_datastore_v3_stub()
    self.testbed.init_mail_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_taskqueue_stub(root_path=_QUEUE_YAML_DIR)
    self.testbed.init_user_stub()
    self.testbed.init_urlfetch_stub()
    ndb.get_context().clear_cache()

    self.mail_stub = self.testbed.get_stub(testbed.MAIL_SERVICE_NAME)
    self.mock_get_request = None
    self._PatchIsInternalUser()
    datastore_hooks.InstallHooks()
    SetIsInternalUser(INTERNAL_USER, True)
    SetIsInternalUser(EXTERNAL_USER, False)
    self.testapp = None
    self.logger = logging.getLogger()
    self.logger.level = logging.DEBUG
    self.stream_handler = logging.StreamHandler(sys.stdout)
    self.logger.addHandler(self.stream_handler)
    self.addCleanup(self.logger.removeHandler, self.stream_handler)

  def SetUpApp(self, handlers):
    self.testapp = webtest.TestApp(webapp2.WSGIApplication(handlers))

  def PatchEnviron(self, path):
    environ_patch = {'REQUEST_URI': path}
    try:
      if oauth.get_current_user(utils.OAUTH_SCOPES):
        # SetCurrentUserOAuth mocks oauth.get_current_user() directly. That
        # function would normally parse this header. If the header doesn't
        # exist (which happens in production when the user isn't signed in), it
        # would normally raise an error that would be difficult to distinguish
        # from when the header exists but is invalid (which should return HTTP
        # 401), so utils.GetEmail() checks for this header and returns
        # None early if it doesn't exist.  If this function's caller has called
        # SetCurrentUserOAuth, then fake this header so that GetEmail
        # proceeds to call oauth.get_current_user().
        environ_patch['HTTP_AUTHORIZATION'] = ''
    except oauth.Error:
      pass
    return mock.patch.dict(os.environ, environ_patch)

  def Post(self, path, *args, **kwargs):
    with self.PatchEnviron(path):
      return self.testapp.post(path, *args, **kwargs)

  def ExecuteTaskQueueTasks(self, handler_name, task_queue_name, recurse=True):
    """Executes all of the tasks on the queue until there are none left."""
    tasks = self.GetTaskQueueTasks(task_queue_name)
    task_queue = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    task_queue.FlushQueue(task_queue_name)
    responses = []
    for task in tasks:
      responses.append(
          self.Post(
              handler_name,
              urllib.unquote_plus(base64.b64decode(task['body']))))
      if recurse:
        responses.extend(
            self.ExecuteTaskQueueTasks(handler_name, task_queue_name))
    return responses

  def ExecuteDeferredTasks(self, task_queue_name, recurse=True):
    task_queue = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = task_queue.GetTasks(task_queue_name)
    task_queue.FlushQueue(task_queue_name)
    for task in tasks:
      deferred.run(base64.b64decode(task['body']))
      if recurse:
        self.ExecuteDeferredTasks(task_queue_name)

  def GetTaskQueueTasks(self, task_queue_name):
    task_queue = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    return task_queue.GetTasks(task_queue_name)

  def SetCurrentUser(self, email, user_id='123456', is_admin=False):
    """Sets the user in the environment in the current testbed."""
    self.testbed.setup_env(
        user_is_admin=('1' if is_admin else '0'),
        user_email=email,
        user_id=user_id,
        overwrite=True)

  def PatchObject(self, obj, prop, value):
    patch = mock.patch.object(obj, prop, value)
    patch.start()
    self.addCleanup(patch.stop)

  def SetCurrentUserOAuth(self, user):
    self.PatchObject(oauth, 'get_current_user', mock.Mock(
        return_value=user))

  def SetCurrentClientIdOAuth(self, client_id):
    self.PatchObject(oauth, 'get_client_id', mock.Mock(return_value=client_id))

  def UnsetCurrentUser(self):
    """Sets the user in the environment to have no email and be non-admin."""
    self.testbed.setup_env(
        user_is_admin='0', user_email='', user_id='', overwrite=True)

  def GetEmbeddedVariable(self, response, var_name):
    """Gets a variable embedded in a script element in a response.

    If the variable was found but couldn't be parsed as JSON, this method
    has a side-effect of failing the test.

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
      match = re.search(var_name + r'\s*=\s*(.+);\s*$', contents,
                        re.MULTILINE)
      if match:
        javascript_value = match.group(1)
        try:
          return json.loads(javascript_value)
        except ValueError:
          self.fail('Could not deserialize value of "%s" as JSON:\n%s' %
                    (var_name, javascript_value))
          return None
    return None

  def GetJsonValue(self, response, key):
    return json.loads(response.body).get(key)

  def PatchDatastoreHooksRequest(self, remote_addr=None):
    """This patches the request object to allow IP address to be set.

    It should be used by tests which check code that does IP address checking
    through datastore_hooks.
    """
    get_request_patcher = mock.patch(
        'webapp2.get_request',
        mock.MagicMock(return_value=FakeRequestObject(remote_addr)))
    self.mock_get_request = get_request_patcher.start()
    self.addCleanup(get_request_patcher.stop)

  def _PatchIsInternalUser(self):
    """Sets up a fake version of utils.IsInternalUser to use in tests.

    This version doesn't try to make any requests to check whether the
    user is internal; it just checks for cached values and returns False
    if nothing is found.
    """
    def IsInternalUser():
      return bool(utils.GetCachedIsInternalUser(utils.GetEmail()))

    self.PatchObject(utils, 'IsInternalUser', IsInternalUser)


def AddTests(masters, bots, tests_dict):
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
      graph_data.Bot(id=bot_name, parent=master_key).put()
      for test_name in tests_dict:
        test_path = '%s/%s/%s' % (master_name, bot_name, test_name)
        t = graph_data.TestMetadata(id=test_path)
        t.UpdateSheriff()
        t.put()
        _AddSubtest(test_path, tests_dict[test_name])


def _AddSubtest(parent_test_path, subtests_dict):
  """Helper function to recursively add sub-TestMetadatas to a TestMetadata.

  Args:
    parent_test_path: A path to the parent test.
    subtests_dict: A dict of test names to dictionaries of subtests.
  """
  for test_name in subtests_dict:
    test_path = '%s/%s' % (parent_test_path, test_name)
    t = graph_data.TestMetadata(id=test_path)
    t.UpdateSheriff()
    t.put()
    _AddSubtest(test_path, subtests_dict[test_name])


def AddRows(test_path, rows):
  """Adds Rows to a given test.

  Args:
    test_path: Full test path of TestMetadata entity to add Rows to.
    rows: Either a dict mapping ID (revision) to properties, or a set of IDs.

  Returns:
    The list of Row entities which have been put, in order by ID.
  """
  test_key = utils.TestKey(test_path)
  container_key = utils.GetTestContainerKey(test_key)
  if isinstance(rows, dict):
    return _AddRowsFromDict(container_key, rows)
  return _AddRowsFromIterable(container_key, rows)


def _AddRowsFromDict(container_key, row_dict):
  """Adds a set of Rows given a dict of revisions to properties."""
  rows = []
  for int_id in sorted(row_dict):
    rows.append(
        graph_data.Row(id=int_id, parent=container_key, **row_dict[int_id]))
  ndb.Future.wait_all(
      [r.put_async() for r in rows] + [rows[0].UpdateParentAsync()])
  return rows


def _AddRowsFromIterable(container_key, row_ids):
  """Adds a set of Rows given an iterable of ID numbers."""
  rows = []
  for int_id in sorted(row_ids):
    rows.append(graph_data.Row(id=int_id, parent=container_key, value=int_id))
  ndb.Future.wait_all(
      [r.put_async() for r in rows] + [rows[0].UpdateParentAsync()])
  return rows


def SetIsInternalUser(user, is_internal_user):
  """Sets the domain that users who can access internal data belong to."""
  utils.SetCachedIsInternalUser(user, is_internal_user)


def SetIsAdministrator(user, is_administrator):
  """Marks the user an an administrator."""
  utils.SetCachedIsAdministrator(user, is_administrator)


def SetSheriffDomains(domains):
  """Sets the domain that users who can access internal data belong to."""
  stored_object.Set(utils.SHERIFF_DOMAINS_KEY, domains)


def SetIpWhitelist(ip_addresses):
  """Sets the list of whitelisted IP addresses."""
  stored_object.Set(utils.IP_WHITELIST_KEY, ip_addresses)
