# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators
from telemetry.core import bitmap
from telemetry.core import util
from telemetry.core import video


class VideoTest(unittest.TestCase):

  @decorators.Enabled('linux')
  def testFramesFromMp4(self):
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

    with open(vid) as video_file:
      video_obj = video.Video(video_file)

      # Calling _FramesFromMp4 should return all frames.
      # pylint: disable=W0212
      for i, timestamp_bitmap in enumerate(video_obj._FramesFromMp4()):
        timestamp, bmp = timestamp_bitmap
        self.assertEquals(timestamp, expected_timestamps[i])
        expected_bitmap = bitmap.Bitmap.FromPngFile(os.path.join(
            util.GetUnittestDataDir(), 'frame%d.png' % i))
        self.assertTrue(expected_bitmap.IsEqual(bmp))
