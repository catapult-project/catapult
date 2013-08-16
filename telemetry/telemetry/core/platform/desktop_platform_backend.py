# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

from telemetry.core import util
from telemetry.core.platform import platform_backend


class DesktopPlatformBackend(platform_backend.PlatformBackend):

  # This is an abstract class. It is OK to have abstract methods.
  # pylint: disable=W0223

  def GetFlushUtilityName(self):
    return NotImplementedError()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    assert directory and os.path.exists(directory), \
        'Target directory %s must exist' % directory
    flush_command = util.FindSupportBinary(self.GetFlushUtilityName())
    assert flush_command, \
        'You must build %s first' % self.GetFlushUtilityName()

    args = [flush_command, '--recurse']
    directory_contents = os.listdir(directory)
    for item in directory_contents:
      if not ignoring or item not in ignoring:
        args.append(os.path.join(directory, item))

    if len(args) < 3:
      return

    p = subprocess.Popen(args)
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'
