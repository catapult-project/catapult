# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Hooks that apply globally to all scripts that import or use Telemetry."""
import atexit
import os
import signal
import sys
import logging

from telemetry.internal.util import exception_formatter


def InstallHooks():
  InstallUnhandledExceptionFormatter()
  InstallStackDumpOnSigusr1()
  InstallTerminationHook()
  InstallListStrayProcessesUponExitHook()

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


def InstallListStrayProcessesUponExitHook():
  def _ListAllSubprocesses():
    try:
      import psutil
    except ImportError:
      logging.error(
          'psutil is not installed on the system. Not listing possible '
          'leaked processes. To install psutil, see: '
          'https://pypi.python.org/pypi/psutil')
    telemetry_pid = os.getpid()
    parent = psutil.Process(telemetry_pid)
    if hasattr(parent, 'children'):
      children = parent.children(recursive=True)
    else:  # Some old version of psutil use get_children instead children.
      children = parent.get_children()
    if children:
      leak_processes_info = []
      for p in children:
        process_info = '%s (%s)' % (p.name(), p.pid)
        try:
          process_info += ' - %s' % p.cmdline()
        except Exception:
          pass
        leak_processes_info.append(process_info)
      logging.error('Telemetry leaks these processes: %s',
                    ', '.join(leak_processes_info))

  atexit.register(_ListAllSubprocesses)
