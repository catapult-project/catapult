# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import platform

from telemetry.internal.backends.chrome import minidump_symbolizer


class CrOSMinidumpSymbolizer(minidump_symbolizer.MinidumpSymbolizer):
  def __init__(self, dump_finder, build_dir):
    """Class for handling all minidump symbolizing code on ChromeOS.

    Args:
      dump_finder: The minidump_finder.MinidumpFinder instance that is being
          used to find minidumps for the test.
      build_dir: The directory containing Chromium build artifacts to generate
          symbols from.
    """
    super(CrOSMinidumpSymbolizer, self).__init__(
        'linux', platform.machine(), dump_finder, build_dir)

  def SymbolizeMinidump(self, minidump):
    if platform.system() != 'Linux' and platform.system() != 'Darwin':
      logging.warning('Cannot get stack traces unless running on a Posix host.')
      return None
    if not self._build_dir:
      logging.warning('Cannot get stack traces unless '
                      '--chromium-output-directory is specified.')
      return None
    return super(CrOSMinidumpSymbolizer, self).SymbolizeMinidump(minidump)

  def GetSymbolBinaries(self, minidump):
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    del minidump  # unused.
    return [os.path.join(self._build_dir, 'chrome')]

  def GetBreakpadPlatformOverride(self):
    """Returns the platform to be passed to generate_breakpad_symbols."""
    return 'chromeos'
