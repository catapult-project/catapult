# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Hooks that apply globally to all scripts that import or use Telemetry."""

import os
import signal
import sys

from telemetry.core import util
from telemetry.util import exception_formatter


def InstallHooks():
  RemoveAllStalePycFiles(util.GetTelemetryDir())
  RemoveAllStalePycFiles(util.GetBaseDir())
  InstallUnhandledExceptionFormatter()
  InstallStackDumpOnSigusr1()
  InstallTerminationHook()


def RemoveAllStalePycFiles(base_dir):
  """Scan directories for old .pyc files without a .py file and delete them."""
  for dirname, _, filenames in os.walk(base_dir):
    if '.svn' in dirname or '.git' in dirname:
      continue
    for filename in filenames:
      root, ext = os.path.splitext(filename)
      if ext != '.pyc':
        continue

      pyc_path = os.path.join(dirname, filename)
      py_path = os.path.join(dirname, root + '.py')

      try:
        if not os.path.exists(py_path):
          os.remove(pyc_path)
      except OSError:
        # Wrap OS calls in try/except in case another process touched this file.
        pass

    try:
      os.removedirs(dirname)
    except OSError:
      # Wrap OS calls in try/except in case another process touched this dir.
      pass


def InstallUnhandledExceptionFormatter():
  """Print prettier exceptions that also contain the stack frame's locals."""
  sys.excepthook = exception_formatter.PrintFormattedException


def InstallStackDumpOnSigusr1():
  """Catch SIGUSR1 and print a stack trace."""
  # Windows doesn't define SIGUSR1.
  if not hasattr(signal, 'SIGUSR1'):
    return

  def PrintDiagnostics(_, stack_frame):
    exception_string = 'SIGUSR1 received, printed stack trace'
    exception_formatter.PrintFormattedFrame(stack_frame, exception_string)
  signal.signal(signal.SIGUSR1, PrintDiagnostics)


def InstallTerminationHook():
  """Catch SIGTERM, print a stack trace, and exit."""
  def PrintStackAndExit(sig, stack_frame):
    exception_string = 'Received signal %s, exiting' % sig
    exception_formatter.PrintFormattedFrame(stack_frame, exception_string)
    sys.exit(-1)
  signal.signal(signal.SIGTERM, PrintStackAndExit)
