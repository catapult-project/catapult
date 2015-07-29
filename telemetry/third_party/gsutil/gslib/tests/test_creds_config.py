# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.
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
"""Tests for various combinations of configured credentials."""

from gslib.cred_types import CredTypes
from gslib.exception import CommandException
from gslib.gcs_json_api import GcsJsonApi
from gslib.tests.mock_logging_handler import MockLoggingHandler
import gslib.tests.testcase as testcase
from gslib.tests.util import SetBotoConfigForTest


class TestCredsConfig(testcase.GsUtilUnitTestCase):
  """Tests for various combinations of configured credentials."""

  def setUp(self):
    super(TestCredsConfig, self).setUp()
    self.log_handler = MockLoggingHandler()
    self.logger.addHandler(self.log_handler)

  def testMultipleConfiguredCreds(self):
    with SetBotoConfigForTest([
        ('Credentials', 'gs_oauth2_refresh_token', 'foo'),
        ('Credentials', 'gs_service_client_id', 'bar'),
        ('Credentials', 'gs_service_key_file', 'baz')]):

      try:
        GcsJsonApi(None, self.logger)
        self.fail('Succeeded with multiple types of configured creds.')
      except CommandException, e:
        msg = str(e)
        self.assertIn('types of configured credentials', msg)
        self.assertIn(CredTypes.OAUTH2_USER_ACCOUNT, msg)
        self.assertIn(CredTypes.OAUTH2_SERVICE_ACCOUNT, msg)

  def testExactlyOneInvalid(self):
    with SetBotoConfigForTest([
        ('Credentials', 'gs_oauth2_refresh_token', 'foo'),
        ('Credentials', 'gs_service_client_id', None),
        ('Credentials', 'gs_service_key_file', None)]):
      succeeded = False
      try:
        GcsJsonApi(None, self.logger)
        succeeded = True  # If we self.fail() here, the except below will catch
      except:  # pylint: disable=bare-except
        warning_messages = self.log_handler.messages['warning']
        self.assertEquals(1, len(warning_messages))
        self.assertIn('credentials are invalid', warning_messages[0])
        self.assertIn(CredTypes.OAUTH2_USER_ACCOUNT, warning_messages[0])
      if succeeded:
        self.fail('Succeeded with invalid credentials, one configured.')
