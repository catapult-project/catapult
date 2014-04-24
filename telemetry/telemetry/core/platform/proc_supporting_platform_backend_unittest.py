# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import logging
import unittest

from telemetry.core import util
from telemetry.core.platform import proc_supporting_platform_backend


class TestBackend(
    proc_supporting_platform_backend.ProcSupportingPlatformBackend):

  # pylint: disable=W0223

  def __init__(self):
    super(TestBackend, self).__init__()
    self._mock_files = {}

  def SetMockFile(self, filename, output):
    self._mock_files[filename] = output

  def _GetFileContents(self, filename):
    return self._mock_files[filename]


class ProcSupportingPlatformBackendTest(unittest.TestCase):

  def testGetMemoryStatsBasic(self):
    if not proc_supporting_platform_backend.resource:
      logging.warning('Test not supported')
      return

    backend = TestBackend()
    with open(os.path.join(util.GetUnittestDataDir(), 'stat')) as f:
      backend.SetMockFile('/proc/1/stat', f.read())
    with open(os.path.join(util.GetUnittestDataDir(), 'status')) as f:
      backend.SetMockFile('/proc/1/status', f.read())
    with open(os.path.join(util.GetUnittestDataDir(), 'smaps')) as f:
      backend.SetMockFile('/proc/1/smaps', f.read())
    result = backend.GetMemoryStats(1)
    self.assertEquals(result, {'PrivateDirty': 5324800,
                               'VM': 1025978368,
                               'VMPeak': 1050099712,
                               'WorkingSetSize': 84000768,
                               'WorkingSetSizePeak': 144547840})

  def testGetMemoryStatsNoHWM(self):
    if not proc_supporting_platform_backend.resource:
      logging.warning('Test not supported')
      return

    backend = TestBackend()
    with open(os.path.join(util.GetUnittestDataDir(), 'stat')) as f:
      backend.SetMockFile('/proc/1/stat', f.read())
    with open(os.path.join(util.GetUnittestDataDir(), 'status_nohwm')) as f:
      backend.SetMockFile('/proc/1/status', f.read())
    with open(os.path.join(util.GetUnittestDataDir(), 'smaps')) as f:
      backend.SetMockFile('/proc/1/smaps', f.read())
    result = backend.GetMemoryStats(1)
    self.assertEquals(result, {'PrivateDirty': 5324800,
                               'VM': 1025978368,
                               'VMPeak': 1025978368,
                               'WorkingSetSize': 84000768,
                               'WorkingSetSizePeak': 84000768})
