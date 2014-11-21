# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.util import cloud_storage

class CloudStorageUnitTest(unittest.TestCase):

  def _FakeRunCommand(self, cmd):
    pass

  def testValidCloudUrl(self):
    cloud_storage._RunCommand = self._FakeRunCommand
    remote_path = 'test-remote-path.html'
    local_path = 'test-local-path.html'
    cloud_url = cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET,
                                     remote_path, local_path)
    self.assertEqual('https://console.developers.google.com/m/cloudstorage'
                     '/b/chromium-telemetry/o/test-remote-path.html',
                     cloud_url)
