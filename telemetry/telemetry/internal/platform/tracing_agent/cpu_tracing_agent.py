# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
try:
  import psutil
except ImportError:
  psutil = None
import subprocess
from threading import Timer

from py_trace_event import trace_time
from telemetry.internal.platform import tracing_agent
from telemetry.timeline import trace_data

DEFAULT_MIN_PCPU = 0.1

class ProcessCollector(object):

  def __init__(self, min_pcpu):
    self._min_pcpu = min_pcpu

  def GetProcesses(self):
    return NotImplemented

class UnixProcessCollector(ProcessCollector):

  _SHELL_COMMAND = NotImplemented
  _START_LINE_NUMBER = 1

  def __init__(self, min_pcpu):
    super(UnixProcessCollector, self).__init__(min_pcpu)

  def _ParseLine(self, line):
    """Parses a line from `ps` output."""


    token_list = line.strip().split()
    if len(token_list) < 4:
      raise ValueError('Line has too few tokens: %s.' % token_list)

    return {
      'pCpu': token_list[0],
      'pMem': token_list[1],
      'pid': token_list[2],
      'name': ' '.join(token_list[3:])
    }

  def GetProcesses(self):
    """Fetches the top processes returned by top command.

    Returns:
      A list of dictionaries, each representing one of the top processes.
    """
    lines = subprocess.check_output(self._SHELL_COMMAND).strip().split('\n')
    process_lines = lines[self._START_LINE_NUMBER:]

    top_processes = []
    for process_line in process_lines:
      process = self._ParseLine(process_line)
      if (not process) or (float(process['pCpu']) < self._min_pcpu):
        continue
      top_processes.append(process)
    return top_processes

class WindowsProcessCollector(ProcessCollector):
  """Class for collecting information about processes on Windows.

  Windows does not have a fast and simple command to list processes, so psutil
  package is used instead."""

  def __init__(self, min_pcpu):
    super(WindowsProcessCollector, self).__init__(min_pcpu)

  def GetProcesses(self):
    data = []
    for p in psutil.process_iter():
      try:
        cpu_percent = p.get_cpu_percent(interval=0)
        if cpu_percent >= self._min_pcpu:
          # Get full path of the process. p.exe often throws AccessDenied
          # and should have its own try block so that the dictionary literal
          # can be added to returned data whether p.exe throws an exception
          # ot not.
          try:
            path = p.exe
          except psutil.Error:
            path = None
          data.append({
            'pCpu': cpu_percent,
            'pMem': p.get_memory_percent(),
            'name': p.name,
            'pid': p.pid,
            'path': path
          })
      except psutil.Error:
        logging.exception('Failed to get process data')
    data = sorted(data, key=lambda d: d['pCpu'],
                  reverse=True)
    return data


class LinuxProcessCollector(UnixProcessCollector):
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


  def __init__(self, min_pcpu):
    super(LinuxProcessCollector, self).__init__(min_pcpu)


class MacProcessCollector(UnixProcessCollector):
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

  def __init__(self, min_pcpu):
    super(MacProcessCollector, self).__init__(min_pcpu)


class CpuTracingAgent(tracing_agent.TracingAgent):

  SNAPSHOT_FREQUENCY = 1.0

  def __init__(self, platform_backend, min_pcpu=DEFAULT_MIN_PCPU):
    super(CpuTracingAgent, self).__init__(platform_backend)
    self._snapshot_ongoing = False
    self._snapshots = []
    self._os_name = platform_backend.GetOSName()
    if  self._os_name == 'win':
      self._collector = WindowsProcessCollector(min_pcpu)
    elif self._os_name == 'mac':
      self._collector = MacProcessCollector(min_pcpu)
    else:
      self._collector = LinuxProcessCollector(min_pcpu)

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
    if self._os_name == 'win' and self._snapshots:
      self._snapshots.pop(0)
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
