# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import inspect
import logging
import os

from py_utils import atexit_with_log


def _GetProcessDescription(process):
  import psutil  # pylint: disable=import-error
  try:
    if inspect.ismethod(process.name):
      name = process.name()
    else:  # Process.name is a property in old versions of psutil.
      name = process.name
    if inspect.ismethod(process.cmdline):
      cmdline = process.cmdline()
    else:
      cmdline = process.cmdline
    return '%s (%s) - %s' % (name, process.pid, cmdline)
  except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied
         ) as e:
    return 'unknown (%s): %r' % (
        process.pid, e)


def ListAllSubprocesses():
  try:
    import psutil
  except ImportError:
    logging.warning(
        'psutil is not installed on the system. Not listing possible '
        'leaked processes. To install psutil, see: '
        'https://pypi.python.org/pypi/psutil')
    return
  telemetry_pid = os.getpid()
  parent = psutil.Process(telemetry_pid)
  if hasattr(parent, 'children'):
    children = parent.children(recursive=True)
  else:  # Some old version of psutil use get_children instead children.
    children = parent.get_children()

  if children:
    processes_info = []
    for p in children:
      processes_info.append(_GetProcessDescription(p))
    logging.warning('Running sub processes (%i processes):\n%s',
                    len(children), '\n'.join(processes_info))


def EnableListingStrayProcessesUponExitHook():
  atexit_with_log.Register(ListAllSubprocesses)
