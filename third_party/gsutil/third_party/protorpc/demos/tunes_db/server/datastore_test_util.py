#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from protorpc import test_util

# DO NOT SUBMIT: Just letting reviewer know that most of this
# came from apphosting/ext/api_testutil.py


class DatastoreTest(test_util.TestCase):
  """Base class for tests that require datastore."""

  __apiproxy_initialized = False

  def setUp(self):
    """Set up the datastore."""
    self.app_id = 'my-app'

    # Set environment variable for app id.
    os.environ['APPLICATION_ID'] = self.app_id

    # Don't use the filesystem with this stub.
    self.datastore_stub = datastore_file_stub.DatastoreFileStub(
        self.app_id, None)

    # Register stub.
    self.ResetApiProxyStubMap()
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', self.datastore_stub)

  def ResetApiProxyStubMap(self):
    """Reset the proxy stub-map.

    Args:
      force: When True, always reset the stubs regardless of their status.

    Must be called before stubs can be configured.

    Every time a new test is created, it is necessary to run with a brand new
    stub.  The problem is that RegisterStub won't allow stubs to be replaced.
    If the global instance is not reset, it raises an exception when a run a
    new test gets run that wants to use a new stub.

    Calling this method more than once per APITest instance will only cause
    a new stub-map to be created once.  Therefore it is called automatically
    during each Configure method.
    """
    if self.__apiproxy_initialized:
      return
    self.__apiproxy_initialized = True
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.GetDefaultAPIProxy()
