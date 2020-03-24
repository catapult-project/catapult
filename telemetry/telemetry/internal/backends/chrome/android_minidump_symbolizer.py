# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import platform
import re
import subprocess

from telemetry.internal.backends.chrome import minidump_symbolizer
from telemetry.internal.results import artifact_logger


class AndroidMinidumpSymbolizer(minidump_symbolizer.MinidumpSymbolizer):
  def __init__(self, dump_finder, build_dir, symbols_dir=None):
    """Class for handling all minidump symbolizing code on Android.

    Args:
      dump_finder: The minidump_finder.MinidumpFinder instance that is being
          used to find minidumps for the test.
      build_dir: The directory containing Chromium build artifacts to generate
          symbols from.
      symbols_dir: An optional path to a directory to store symbols for re-use.
          Re-using symbols will result in faster symbolization times, but the
          provided directory *must* be unique per browser binary, e.g. by
          including the hash of the binary in the directory name.
    """
    # We use the OS/arch of the host, not the device.
    super(AndroidMinidumpSymbolizer, self).__init__(
        platform.system().lower(), platform.machine(), dump_finder, build_dir,
        symbols_dir=symbols_dir)

  def SymbolizeMinidump(self, minidump):
    if platform.system() != 'Linux':
      logging.warning(
          'Cannot get Android stack traces unless running on a Posix host.')
      return None
    if not self._build_dir:
      logging.warning(
          'Cannot get Android stack traces without build directory.')
      return None
    return super(AndroidMinidumpSymbolizer, self).SymbolizeMinidump(minidump)

  def GetSymbolBinaries(self, minidump):
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    libraries = self._ExtractLibraryNamesFromDump(minidump)
    return [os.path.join(
        self._build_dir, 'lib.unstripped', lib) for lib in libraries]

  def GetBreakpadPlatformOverride(self):
    return 'android'

  def _ExtractLibraryNamesFromDump(self, minidump):
    """Extracts library names that may contain symbols from the minidump.

    This is a duplicate of the logic in Chromium's
    //build/android/stacktrace/crashpad_stackwalker.py.

    Returns:
      A list of strings containing library names of interest for symbols.
    """
    default_library_name = 'libmonochrome.so'
    dumper_path = os.path.join(self._build_dir, 'minidump_dump')
    if not os.access(dumper_path, os.X_OK):
      logging.warning(
          'Cannot extract library name from dump because %s is not found, '
          'default to: %s', dumper_path, default_library_name)
      return [default_library_name]

    stdout = None
    try:
      stdout = subprocess.check_output(
          [dumper_path, minidump], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
      stdout = e.output
      # Dumper errors often do not affect stack walkability, just a warning.
      # It's possible for the same stack to be symbolized multiple times, so
      # add a timestamp suffix to prevent artifact collisions.
      now = datetime.datetime.now()
      suffix = now.strftime('%Y-%m-%d-%H-%M-%S')
      artifact_name = 'dumper_errors/%s-%s' % (
          os.path.basename(minidump), suffix)
      logging.warning(
          'Reading minidump failed, but likely not actually an issue. Saving '
          'output to artifact %s', artifact_name)
      artifact_logger.CreateArtifact(artifact_name, stdout)

    library_names = []
    module_library_line_re = re.compile(r'[(]code_file[)]\s+= '
                                        r'"(?P<library_name>lib[^. ]+.so)"')
    in_module = False
    for line in stdout.splitlines():
      line = line.lstrip().rstrip('\n')
      if line == 'MDRawModule':
        in_module = True
        continue
      if line == '':
        in_module = False
        continue
      if in_module:
        m = module_library_line_re.match(line)
        if m:
          library_names.append(m.group('library_name'))
    if not library_names:
      logging.warning(
          'Could not find any library name in the dump, '
          'default to: %s', default_library_name)
      return [default_library_name]
    return library_names
