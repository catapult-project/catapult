# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators

from telemetry.unittest_util import system_stub
from telemetry.util import cloud_storage


def _FakeFindGsutil():
  return 'fake gsutil path'


class CloudStorageUnitTest(unittest.TestCase):

  def _FakeRunCommand(self, cmd):
    pass

  def testValidCloudUrl(self):
    orig_run_command = cloud_storage._RunCommand
    try:
      cloud_storage._RunCommand = self._FakeRunCommand
      remote_path = 'test-remote-path.html'
      local_path = 'test-local-path.html'
      cloud_url = cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET,
                                       remote_path, local_path)
      self.assertEqual('https://console.developers.google.com/m/cloudstorage'
                       '/b/chromium-telemetry/o/test-remote-path.html',
                       cloud_url)
    finally:
      cloud_storage._RunCommand = orig_run_command

  def testExistsReturnsFalse(self):
    stubs = system_stub.Override(cloud_storage, ['subprocess'])
    orig_find_gs_util = cloud_storage.FindGsutil
    try:
      stubs.subprocess.Popen.communicate_result = (
        '',
        'CommandException: One or more URLs matched no objects.\n')
      stubs.subprocess.Popen.returncode_result = 1
      cloud_storage.FindGsutil = _FakeFindGsutil
      self.assertFalse(cloud_storage.Exists('fake bucket',
                                            'fake remote path'))
    finally:
      stubs.Restore()
      cloud_storage.FindGsutil = orig_find_gs_util
