# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
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

class ProcessCollector(object):

  def __init__(self, process_count):
    self._process_count = process_count

  def GetProcesses(self):
    return NotImplemented

class UnixProcessCollector(ProcessCollector):

  _SHELL_COMMAND = NotImplemented
  _START_LINE_NUMBER = 1
  _TOKEN_COUNT = 4
  _TOKEN_MAP = {
    'pCpu': 2,
    'pid': 0,
    'pMem': 3,
    'command': 1
  }

  def __init__(self, process_count, binary_output=False):
    super(UnixProcessCollector, self).__init__(process_count)
    self._binary_output = binary_output

  def _ParseLine(self, line):
    """Parses a line from top output

    Args:
      line(str): a line from top output that contains the information about a
                 process.

    Returns:
      An dictionary with useful information about the process.
    """
    token_list = line.strip().split()
    if len(token_list) != self._TOKEN_COUNT:
      return None
    return {attribute_name: token_list[index]
            for attribute_name, index in self._TOKEN_MAP.items()}

  def GetProcesses(self):
    """Fetches the top processes returned by top command.

    Returns:
      A list of dictionaries, each representing one of the top processes.
    """
    if self._binary_output:
      processes = subprocess.check_output(self._SHELL_COMMAND).decode(
        'ascii').split('\n')
    else:
      processes = subprocess.check_output(self._SHELL_COMMAND).split('\n')
    process_lines = processes[self._START_LINE_NUMBER:]
    top_processes = []
    for process_line in process_lines:
      process = self._ParseLine(process_line)
      if not process:
        continue
      top_processes.append(process)
      if len(top_processes) >= self._process_count:
        break
    return top_processes


class WindowsProcessCollector(ProcessCollector):
  """Class for collecting information about processes on Windows.

  Windows does not have a fast and simple command to list processes, so psutil
  package is used instead."""

  def __init__(self, process_count=20):
    super(WindowsProcessCollector, self).__init__(process_count)

  def GetProcesses(self):
    data = []
    for p in psutil.process_iter():
      try:
        data.append({
          'pCpu': p.get_cpu_percent(interval=0),
          'pMem': p.get_memory_percent(),
          'command': p.name,
          'pid': p.pid
        })
      except psutil.Error:
        pass
    data = sorted(data, key=lambda d: d['pCpu'],
                  reverse=True)[0: self._process_count]
    return data


class LinuxProcessCollector(UnixProcessCollector):
  """Class for collecting information about processes on Linux.

  Example of Linux command output: '31887 com.app.Webkit 3.4 8.0'"""

  _SHELL_COMMAND = ["ps", "axo", "pid,cmd,pcpu,pmem", "--sort=-pcpu"]


  def __init__(self, process_count=20):
    super(LinuxProcessCollector, self).__init__(process_count)


class MacProcessCollector(UnixProcessCollector):
  """Class for collecting information about processes on Mac.

  Example of Mac command output:
  '31887 com.app.Webkit 3.4 8.0'"""

  _SHELL_COMMAND = ['ps', '-arcwwwxo', 'pid command %cpu %mem']

  def __init__(self, process_count=20):
    super(MacProcessCollector, self).__init__(process_count, binary_output=True)


class CpuTracingAgent(tracing_agent.TracingAgent):

  SNAPSHOT_FREQUENCY = 1.0

  def __init__(self, platform_backend):
    super(CpuTracingAgent, self).__init__(platform_backend)
    self._snapshot_ongoing = False
    self._snapshots = []
    os_name = platform_backend.GetOSName()
    if  os_name == 'win':
      self._collector = WindowsProcessCollector()
    elif os_name == 'mac':
      self._collector = MacProcessCollector()
    else:
      self._collector = LinuxProcessCollector()

  @classmethod
  def IsSupported(cls, platform_backend):
    os_name = platform_backend.GetOSName()
    return (os_name in ['mac', 'linux']) or (os_name == 'win' and psutil)

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
    self._snapshots.append((self._collector.GetProcesses(), trace_time.Now()))
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
        'processes': snapshot
      }
    } for snapshot, timestamp in self._snapshots]
