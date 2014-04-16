# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess

from telemetry.core.platform import platform_backend
from telemetry.util import support_binaries


class DesktopPlatformBackend(platform_backend.PlatformBackend):

  # This is an abstract class. It is OK to have abstract methods.
  # pylint: disable=W0223

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    assert directory and os.path.exists(directory), \
        'Target directory %s must exist' % directory
    flush_command = support_binaries.FindPath('clear_system_cache',
                                              self.GetOSName())
    assert flush_command, 'You must build clear_system_cache first'

    args = []
    directory_contents = os.listdir(directory)
    for item in directory_contents:
      if not ignoring or item not in ignoring:
        args.append(os.path.join(directory, item))

    # According to msdn:
    # http://msdn.microsoft.com/en-us/library/ms682425%28VS.85%29.aspx
    # there's a maximum allowable command line of 32,768 characters on windows.
    while args:
      # Small note about [:256] and [256:]
      # [:N] will return a list with the first N elements, ie.
      # with [1,2,3,4,5], [:2] -> [1,2], and [2:] -> [3,4,5]
      # with [1,2,3,4,5], [:5] -> [1,2,3,4,5] and [5:] -> []
      subprocess.check_call([flush_command, '--recurse'] + args[:256])
      args = args[256:]
