# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time

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

    symbol_binaries = self.GetSymbolBinaries(minidump)

    cmds = []
    missing_binaries = []
    for binary_path in symbol_binaries:
      if not os.path.exists(binary_path):
        missing_binaries.append(binary_path)
        continue
      cmd = [
          sys.executable,
          generate_breakpad_symbols_command,
          '--binary=%s' % binary_path,
          '--symbols-dir=%s' % symbols_dir,
          '--build-dir=%s' % self._build_dir,
          ]
      if self.GetBreakpadPlatformOverride():
        cmd.append('--platform=%s' % self.GetBreakpadPlatformOverride())
      cmds.append(cmd)

    if missing_binaries:
      logging.warning(
          'Unable to find %d of %d binaries for minidump symbolization. This '
          'is likely not an actual issue, but is worth investigating if the '
          'minidump fails to symbolize properly.',
          len(missing_binaries), len(symbol_binaries))
      # 5 is arbitrary, but a reasonable number of paths to print out.
      if len(missing_binaries) < 5:
        logging.warning('Missing binaries: %s', missing_binaries)
      else:
        logging.warning(
            'Run test with high verbosity to get the list of missing binaries.')
        logging.debug('Missing binaries: %s', missing_binaries)

    # We need to prevent the number of file handles that we open from reaching
    # the soft limit set for the current process. This can either be done by
    # ensuring that the limit is suitably large using the resource module or by
    # only starting a relatively small number of subprocesses at once. In order
    # to prevent any potential issues with messing with system limits, that
    # latter is chosen.
    # Typically, this would be handled by using the multiprocessing module's
    # pool functionality, but importing generate_breakpad_symbols and invoking
    # it directly takes significantly longer than alternatives for whatever
    # reason, even if they appear to perform more work. Thus, we could either
    # have each task in the pool create its own subprocess that runs the
    # command or manually limit the number of subprocesses we have at any
    # given time. We go with the latter option since it should be less
    # wasteful.
    processes = {}
    # Symbol dumping is somewhat I/O constrained, so use double the number of
    # logical cores on the system.
    process_limit = multiprocessing.cpu_count() * 2
    while len(cmds) or len(processes):
      # Clear any processes that have finished.
      processes_to_delete = []
      for p in processes:
        if p.poll() is not None:
          stdout, _ = p.communicate()
          if p.returncode:
            logging.error(stdout)
            logging.warning('Failed to execute %s', processes[p])
          processes_to_delete.append(p)
      for p in processes_to_delete:
        del processes[p]
      # Add as many more processes as we can.
      while len(processes) < process_limit and len(cmds):
        cmd = cmds.pop(-1)
        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        processes[p] = cmd
      # 1 second is fairly arbitrary, but strikes a reasonable balance between
      # spending too many cycles checking the current state of running
      # processes and letting cores sit idle.
      time.sleep(1)
