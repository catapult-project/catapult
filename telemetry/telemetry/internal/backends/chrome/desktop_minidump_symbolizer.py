# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import subprocess

from telemetry.internal.backends.chrome import minidump_symbolizer
from telemetry.internal.util import binary_manager

class DesktopMinidumpSymbolizer(minidump_symbolizer.MinidumpSymbolizer):
  def __init__(self, os_name, arch_name, dump_finder, build_dir):
    """Class for handling all minidump symbolizing code on Desktop platforms.

    Args:
      os_name: The OS of the test machine.
      arch_name: The arch name of the test machine.
      dump_finder: The minidump_finder.MinidumpFinder instance that is being
          used to find minidumps for the test.
      build_dir: The directory containing Chromium build artifacts to generate
          symbols from.
    """
    super(DesktopMinidumpSymbolizer, self).__init__(
        os_name, arch_name, dump_finder, build_dir)

  def GetSymbolBinaries(self, minidump):
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    minidump_dump = binary_manager.FetchPath(
        'minidump_dump', self._arch_name, self._os_name)
    assert minidump_dump

    symbol_binaries = []

    minidump_cmd = [minidump_dump, minidump]
    try:
      with open(os.devnull, 'wb') as dev_null:
        minidump_output = subprocess.check_output(minidump_cmd, stderr=dev_null)
    except subprocess.CalledProcessError as e:
      # For some reason minidump_dump always fails despite successful dumping.
      minidump_output = e.output

    minidump_binary_re = re.compile(r'\W+\(code_file\)\W+=\W\"(.*)\"')
    for minidump_line in minidump_output.splitlines():
      line_match = minidump_binary_re.match(minidump_line)
      if line_match:
        binary_path = line_match.group(1)
        if not os.path.isfile(binary_path):
          continue

        # Filter out system binaries.
        if (binary_path.startswith('/usr/lib/') or
            binary_path.startswith('/System/Library/') or
            binary_path.startswith('/lib/')):
          continue

        # Filter out other binary file types which have no symbols.
        if (binary_path.endswith('.pak') or
            binary_path.endswith('.bin') or
            binary_path.endswith('.dat') or
            binary_path.endswith('.ttf')):
          continue

        symbol_binaries.append(binary_path)
    return symbol_binaries
