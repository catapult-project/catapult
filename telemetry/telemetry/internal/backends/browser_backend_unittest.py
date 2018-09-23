# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest

from telemetry.internal.backends import browser_backend
from telemetry.testing import browser_test_case
from telemetry.testing import options_for_unittests
import mock


class BrowserBackendLogsUploadingUnittest(unittest.TestCase):
  def testUploadingToCLoudStorage(self):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file_name = temp_file.name
    try:
      temp_file.write('This is a\ntest log file.\n')
      temp_file.close()

      # pylint: disable=abstract-method
      class FakeBrowserBackend(browser_backend.BrowserBackend):
        @property
        def supports_uploading_logs(self):
          return True

        @property
        def log_file_path(self):
          return temp_file_name

      options = options_for_unittests.GetCopy()
      options.browser_options.logging_verbosity = (
          options.browser_options.VERBOSE_LOGGING)
      options.browser_options.logs_cloud_bucket = 'ABC'
      options.browser_options.logs_cloud_remote_path = 'def'

      b = FakeBrowserBackend(
          platform_backend=None, browser_options=options.browser_options,
          supports_extensions=False, tab_list_backend=None)
      self.assertEquals(b.GetLogFileContents(), 'This is a\ntest log file.\n')
      with mock.patch('py_utils.cloud_storage.Insert') as mock_insert:
        b.UploadLogsToCloudStorage()
        mock_insert.assert_called_with(
            bucket='ABC', remote_path='def', local_path=temp_file_name)
    finally:
      os.remove(temp_file_name)


class BrowserBackendIntegrationTest(browser_test_case.BrowserTestCase):
  def setUp(self):
    super(BrowserBackendIntegrationTest, self).setUp()
    self._browser_backend = self._browser._browser_backend

  def testSmokeIsBrowserRunningReturnTrue(self):
    self.assertTrue(self._browser_backend.IsBrowserRunning())

  def testSmokeIsBrowserRunningReturnFalse(self):
    self._browser_backend.Close()
    self.assertFalse(self._browser_backend.IsBrowserRunning())

  def testBrowserPid(self):
    pid = self._browser_backend.GetPid()
    self.assertTrue(self._browser_backend.GetPid())
    self.assertEqual(pid, self._browser_backend.GetPid())
