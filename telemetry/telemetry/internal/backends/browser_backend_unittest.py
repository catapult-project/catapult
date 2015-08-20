# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.internal.backends import browser_backend
from telemetry.testing import options_for_unittests
import mock


class BrowserBackendLogsUploadingUnittest(unittest.TestCase):
  def testUploadingToCLoudStorage(self):
    # pylint: disable=abstract-method
    class FakeBrowserBackend(browser_backend.BrowserBackend):
      @property
      def supports_uploading_logs(self):
        return True

      @property
      def log_file_path(self):
        return '/foo/bar'

    options = options_for_unittests.GetCopy()
    options.browser_options.enable_logging = True
    options.browser_options.logs_cloud_bucket = 'ABC'
    options.browser_options.logs_cloud_remote_path = 'def'

    b = FakeBrowserBackend(None, False, options.browser_options, None)
    with mock.patch('catapult_base.cloud_storage.Insert') as mock_insert:
      b.UploadLogsToCloudStorage()
      mock_insert.assert_called_with(
        bucket='ABC', remote_path='def', local_path='/foo/bar')
