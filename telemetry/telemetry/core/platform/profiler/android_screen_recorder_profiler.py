# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

from telemetry.core import util
from telemetry.core.backends.chrome import android_browser_finder
from telemetry.core.platform import profiler


class AndroidScreenRecordingProfiler(profiler.Profiler):
  """Captures a screen recording on Android."""

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(AndroidScreenRecordingProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)
    self._output_path = output_path + '.mp4'
    self._recorder = subprocess.Popen(
        [os.path.join(util.GetChromiumSrcDir(), 'build', 'android',
                      'screenshot.py'),
         '--video',
         '--file', self._output_path,
         '--device', browser_backend.adb.device_serial()],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)

  @classmethod
  def name(cls):
    return 'android-screen-recorder'

  @classmethod
  def is_supported(cls, browser_type):
    if browser_type == 'any':
      return android_browser_finder.CanFindAvailableBrowsers()
    return browser_type.startswith('android')

  def CollectProfile(self):
    self._recorder.communicate(input='\n')

    print 'Screen recording saved as %s' % self._output_path
    print 'To view, open in Chrome or a video player'
    return [self._output_path]
