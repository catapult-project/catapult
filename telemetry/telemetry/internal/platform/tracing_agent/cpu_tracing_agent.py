# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import subprocess
from threading import Timer

from py_trace_event import trace_time
from telemetry.internal.platform import tracing_agent
from telemetry.timeline import trace_data


def _ParsePsProcessString(line):
  """Parses a process line from the output of `ps`.

  Example of `ps` command output:
  '3.4 8.0 31887 com.app.Webkit'
  """
  token_list = line.strip().split()
  if len(token_list) < 4:
    raise ValueError('Line has too few tokens: %s.' % token_list)

  return {
    'pCpu': float(token_list[0]),
    'pMem': float(token_list[1]),
    'pid': int(token_list[2]),
    'name': ' '.join(token_list[3:])
  }


class ProcessCollector(object):
  def _GetProcessesAsStrings(self):
    """Returns a list of strings, each of which contains info about a
    process.
    """
    raise NotImplementedError

  def _ParseProcessString(self, proc_string):
    """Parses an individual process string returned by _GetProcessesAsStrings().

    Returns:
      A dictionary containing keys of 'pid' (a string process ID), 'name' (a
      string for the process name), 'pCpu' (a float for the percent CPU load
      incurred by the process), and 'pMem' (a float for the percent memory load
      caused by the process).
    """
    raise NotImplementedError

  def GetProcesses(self):
    """Fetches the top processes returned by top command.

    Returns:
      A list of dictionaries, each containing 'pid' (a string process ID), 'name
      (a string for the process name), pCpu' (a float for the percent CPU load
      incurred by the process), and 'pMem' (a float for the percent memory load
      caused by the process).
    """
    proc_strings = self._GetProcessesAsStrings()
    raw_procs = [
        self._ParseProcessString(proc_string) for proc_string in proc_strings
    ]

    # TODO(charliea): Aggregate all processes with the same name into a single
    # entry and add a 'count' key indicating how many processes exist with that
    # name. That way, we can easily see things like "Chrome had 25 processes
    # which, combined, took up 25 percent of memory and 40 percent of CPU".
    return [proc for proc in raw_procs if proc['pCpu'] > 0 or proc['pMem'] > 0]


class WindowsProcessCollector(ProcessCollector):
  """Class for collecting information about processes on Windows."""
  def _GetProcessesAsStrings(self):
    raise NotImplementedError

  def _ParseProcessString(self, proc_string):
    raise NotImplementedError


class LinuxProcessCollector(ProcessCollector):
  """Class for collecting information about processes on Linux.

  Example of Linux command output:
  '3.4 8.0 31887 com.app.Webkit'
  """
  _SHELL_COMMAND = [
    'ps',
    '-a', # Include processes that aren't session leaders.
    '-x', # List all processes, even those not owned by the user.
    '-o', # Show the output in the specified format.
    'pcpu,pmem,pid,cmd'
  ]

  def _GetProcessesAsStrings(self):
    # Skip the header row and strip the trailing newline.
    return subprocess.check_output(self._SHELL_COMMAND).strip().split('\n')[1:]

  def _ParseProcessString(self, proc_string):
    return _ParsePsProcessString(proc_string)


class MacProcessCollector(ProcessCollector):
  """Class for collecting information about processes on Mac.

  Example of Mac command output:
  '3.4 8.0 31887 com.app.Webkit'
  """

  _SHELL_COMMAND = [
    'ps',
    '-a', # Include all users' processes.
    '-ww', # Don't limit the length of each line.
    '-x', # Include processes that aren't associated with a terminal.
    '-o', # Show the output in the specified format.
    '%cpu %mem pid command' # Put the command last to avoid truncation.
  ]

  def _GetProcessesAsStrings(self):
    # Skip the header row and strip the trailing newline.
    return subprocess.check_output(self._SHELL_COMMAND).strip().split('\n')[1:]

  def _ParseProcessString(self, proc_string):
    return _ParsePsProcessString(proc_string)


class CpuTracingAgent(tracing_agent.TracingAgent):

  SNAPSHOT_FREQUENCY = 1.0

  def __init__(self, platform_backend):
    super(CpuTracingAgent, self).__init__(platform_backend)
    self._snapshot_ongoing = False
    self._snapshots = []
    self._os_name = platform_backend.GetOSName()
    if  self._os_name == 'win':
      self._collector = WindowsProcessCollector()
    elif self._os_name == 'mac':
      self._collector = MacProcessCollector()
    else:
      self._collector = LinuxProcessCollector()

  @classmethod
  def IsSupported(cls, platform_backend):
    os_name = platform_backend.GetOSName()
    # TODO(charliea): Reenable this once the CPU tracing agent is fixed on
    # Windows.
    # http://crbug.com/647443
    return (os_name in ['mac', 'linux'])

  def StartAgentTracing(self, config, timeout):
    assert not self._snapshot_ongoing, (
           'Agent is already taking snapshots when tracing is started.')
    if not config.enable_cpu_trace:
      return False
    self._snapshot_ongoing = True
    self._KeepTakingSnapshots()
    return True

  def _KeepTakingSnapshots(self):
    """Take CPU snapshots every SNAPSHOT_FREQUENCY seconds."""
    if not self._snapshot_ongoing:
      return
    # Assume CpuTracingAgent shares the same clock domain as telemetry
    self._snapshots.append(
        (self._collector.GetProcesses(), trace_time.Now()))
    Timer(self.SNAPSHOT_FREQUENCY, self._KeepTakingSnapshots).start()

  def StopAgentTracing(self):
    assert self._snapshot_ongoing, (
           'Agent is not taking snapshots when tracing is stopped.')
    self._snapshot_ongoing = False

  def CollectAgentTraceData(self, trace_data_builder, timeout=None):
    assert not self._snapshot_ongoing, (
           'Agent is still taking snapshots when data is collected.')
    self._snapshot_ongoing = False
    data = json.dumps(self._FormatSnapshotsData())
    trace_data_builder.SetTraceFor(trace_data.CPU_TRACE_DATA, data)

  def _FormatSnapshotsData(self):
    """Format raw data into Object Event specified in Trace Format document."""
    pid = os.getpid()
    return [{
      'name': 'CPUSnapshots',
      'ph': 'O',
      'id': '0x1000',
      'local': True,
      'ts': timestamp,
      'pid': pid,
      'tid':None,
      'args': {
        'snapshot':{
          'processes': snapshot
        }
      }
    } for snapshot, timestamp in self._snapshots]
