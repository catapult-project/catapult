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

class ProcessCollector(object):

  _SHELL_COMMAND = NotImplemented
  _START_LINE_NUMBER = NotImplemented
  _TOKEN_COUNT = NotImplemented
  _TOKEN_MAP = NotImplemented

  def __init__(self, process_count, binary_output=False):
    self._process_count = process_count
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
  """Class for collecting information about processes in Linux.
  Example of Windows command output:
  '353 57 263132 252940 597 4.55 4248 chrome'"""

  _SHELL_COMMAND = [
    'c:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe',
    'ps | sort -desc cpu']
  _START_LINE_NUMBER = 3
  _TOKEN_COUNT = 8
  _TOKEN_MAP = {
    'pCpu': 5,
    'pid': 6,
    'command': 7
  }

  def __init__(self, process_count=20):
    super(WindowsProcessCollector, self).__init__(process_count)


class LinuxProcessCollector(ProcessCollector):
  """Class for collecting information about processes in Linux.
  Example of Linux command output:
  '1900 root 20 0 671888 56460 6828 S 6.2 0.2 0:33.95 gagentd'"""

  _SHELL_COMMAND = ['top', '-n 1', '-b']
  _START_LINE_NUMBER = 7
  _TOKEN_COUNT = 12
  _TOKEN_MAP = {
    'pCpu': 8,
    'pid': 0,
    'pMem': 9,
    'command': 11
  }

  def __init__(self, process_count=20):
    super(LinuxProcessCollector, self).__init__(process_count)


class MacProcessCollector(ProcessCollector):
  """Class for collecting information about processes in Mac.
  Example of Mac command output:
  '31887 com.app.Webkit 3.4 8.0'"""

  _SHELL_COMMAND = ['ps', '-arcwwwxo', 'pid command %cpu %mem']
  _START_LINE_NUMBER = 1
  _TOKEN_COUNT = 4
  _TOKEN_MAP = {
    'pCpu': 2,
    'pid': 0,
    'pMem': 3,
    'command': 1
  }

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
      self._parser = WindowsProcessCollector()
    elif os_name == 'mac':
      self._parser = MacProcessCollector()
    else:
      self._parser = LinuxProcessCollector()

  @classmethod
  def IsSupported(cls, platform_backend):
    # TODO(ziqi): enable supports on win (https://github.com/catapult-project/catapult/issues/2439)
    return platform_backend.GetOSName() in ['linux', 'mac']

  def StartAgentTracing(self, config, timeout):
    assert not self._snapshot_ongoing, \
           'Agent is already taking snapshots when tracing is startex.'
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
    self._snapshots.append((self._parser.GetProcesses(), trace_time.Now()))
    Timer(self.SNAPSHOT_FREQUENCY, self._KeepTakingSnapshots).start()

  def StopAgentTracing(self):
    assert self._snapshot_ongoing, \
           'Agent is not taking snapshots when tracing is stopped.'
    self._snapshot_ongoing = False

  def CollectAgentTraceData(self, trace_data_builder, timeout=None):
    assert self._snapshot_ongoing, \
           'Agent is not taking snapshots when data is collected.'
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
