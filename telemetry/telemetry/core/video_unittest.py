# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import unittest

from telemetry import test
from telemetry.core import bitmap
from telemetry.core import util
from telemetry.core import video
from telemetry.core.platform import android_platform_backend
from telemetry.unittest import system_stub

class MockAdbCommands(object):
  def CanAccessProtectedFileContents(self):
    return True

class MockDevice(object):
  def __init__(self, mock_adb_commands):
    self.old_interface = mock_adb_commands

class VideoTest(unittest.TestCase) :
  def setUp(self):
    self._stubs = system_stub.Override(android_platform_backend,
                                       ['perf_control', 'thermal_throttle'])

  def tearDown(self):
    self._stubs.Restore()

  @test.Disabled
  def testFramesFromMp4(self):
    mock_adb = MockDevice(MockAdbCommands())
    backend = android_platform_backend.AndroidPlatformBackend(mock_adb, False)

    try:
      backend.InstallApplication('avconv')
    finally:
      if not backend.CanLaunchApplication('avconv'):
        logging.warning('Test not supported on this platform')
        return  # pylint: disable=W0150

    vid = os.path.join(util.GetUnittestDataDir(), 'vid.mp4')
    expected_timestamps = [
      0,
      763,
      783,
      940,
      1715,
      1732,
      1842,
      1926,
      ]

    video_obj = video.Video(backend, vid)

    # Calling _FramesFromMp4 should return all frames.
    # pylint: disable=W0212
    for i, timestamp_bitmap in enumerate(video_obj._FramesFromMp4(vid)):
      timestamp, bmp = timestamp_bitmap
      self.assertEquals(timestamp, expected_timestamps[i])
      expected_bitmap = bitmap.Bitmap.FromPngFile(os.path.join(
          util.GetUnittestDataDir(), 'frame%d.png' % i))
      self.assertTrue(expected_bitmap.IsEqual(bmp))
