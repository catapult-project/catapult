# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

from telemetry.internal.util import binary_manager


class MinidumpSymbolizer(object):
  def __init__(self, os_name, arch_name, dump_finder, build_dir):
    """Abstract class for handling all minidump symbolizing code.

    Args:
      os_name: The OS of the host (if running the test on a device), or the OS
          of the test machine (if running the test locally).
      arch_name: The arch name of the host (if running the test on a device), or
          the OS of the test machine (if running the test locally).
      dump_finder: The minidump_finder.MinidumpFinder instance that is being
          used to find minidumps for the test.
      build_dir: The directory containing Chromium build artifacts to generate
          symbols from.
    """
    self._os_name = os_name
    self._arch_name = arch_name
    self._dump_finder = dump_finder
    self._build_dir = build_dir

  def SymbolizeMinidump(self, minidump):
    """Gets the stack trace from the given minidump.

    Args:
      minidump: the path to the minidump on disk

    Returns:
      None if the stack could not be retrieved for some reason, otherwise a
      string containing the stack trace.
    """
    if self._os_name == 'win':
      cdb = self._GetCdbPath()
      if not cdb:
        logging.warning('cdb.exe not found.')
        return None
      # Move to the thread which triggered the exception (".ecxr"). Then include
      # a description of the exception (".lastevent"). Also include all the
      # threads' stacks ("~*kb30") as well as the ostensibly crashed stack
      # associated with the exception context record ("kb30"). Note that stack
      # dumps, including that for the crashed thread, may not be as precise as
      # the one starting from the exception context record.
      # Specify kb instead of k in order to get four arguments listed, for
      # easier diagnosis from stacks.
      output = subprocess.check_output([cdb, '-y', self.browser_directory,
                                        '-c', '.ecxr;.lastevent;kb30;~*kb30;q',
                                        '-z', minidump])
      # The output we care about starts with "Last event:" or possibly
      # other things we haven't seen yet. If we can't find the start of the
      # last event entry, include output from the beginning.
      info_start = 0
      info_start_match = re.search("Last event:", output, re.MULTILINE)
      if info_start_match:
        info_start = info_start_match.start()
      info_end = output.find('quit:')
      return output[info_start:info_end]

    stackwalk = binary_manager.FetchPath(
        'minidump_stackwalk', self._arch_name, self._os_name)
    if not stackwalk:
      logging.warning('minidump_stackwalk binary not found.')
      return None
    # We only want this logic on linux platforms that are still using breakpad.
    # See crbug.com/667475
    if not self._dump_finder.MinidumpObtainedFromCrashpad(minidump):
      with open(minidump, 'rb') as infile:
        minidump += '.stripped'
        with open(minidump, 'wb') as outfile:
          outfile.write(''.join(infile.read().partition('MDMP')[1:]))

    symbols_dir = tempfile.mkdtemp()
    try:
      self._GenerateBreakpadSymbols(symbols_dir, minidump)
      return subprocess.check_output([stackwalk, minidump, symbols_dir],
                                     stderr=open(os.devnull, 'w'))
    finally:
      shutil.rmtree(symbols_dir)

  def GetSymbolBinaries(self, minidump):
    """Returns a list of paths to binaries where symbols may be located.

    Args:
      minidump: The path to the minidump being symbolized.
    """
    raise NotImplementedError()

  def GetBreakpadPlatformOverride(self):
    """Returns the platform to be passed to generate_breakpad_symbols."""
    return None

  def _GenerateBreakpadSymbols(self, symbols_dir, minidump):
    """Generates Breakpad symbols for use with stackwalking tools.

    Args:
      symbols_dir: The directory where symbols will be written to.
      minidump: The path to the minidump being symbolized.
    """
    logging.info('Dumping Breakpad symbols.')
    generate_breakpad_symbols_command = binary_manager.FetchPath(
        'generate_breakpad_symbols', self._arch_name, self._os_name)
    if not generate_breakpad_symbols_command:
      logging.warning('generate_breakpad_symbols binary not found')
      return

    for binary_path in self.GetSymbolBinaries(minidump):
      cmd = [
          sys.executable,
          generate_breakpad_symbols_command,
          '--binary=%s' % binary_path,
          '--symbols-dir=%s' % symbols_dir,
          '--build-dir=%s' % self._build_dir,
          ]
      if self.GetBreakpadPlatformOverride():
        cmd.append('--platform=%s' % self.GetBreakpadPlatformOverride())

      try:
        subprocess.check_output(cmd)
      except subprocess.CalledProcessError as e:
        logging.error(e.output)
        logging.warning('Failed to execute "%s"', ' '.join(cmd))
        return
