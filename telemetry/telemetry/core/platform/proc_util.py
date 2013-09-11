# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms


def _ConvertKbToByte(value):
  return int(value.replace('kB','')) * 1024


def _GetProcFileDict(contents):
  retval = {}
  for line in contents.splitlines():
    key, value = line.split(':')
    retval[key.strip()] = value.strip()
  return retval


def _GetProcJiffies(timer_list):
  """Parse '/proc/timer_list' output and returns the first jiffies attribute.

  Multi-CPU machines will have multiple 'jiffies:' lines, all of which will be
  essentially the same.  Return the first one."""
  if isinstance(timer_list, str):
    timer_list = timer_list.splitlines()
  for line in timer_list:
    if line.startswith('jiffies:'):
      _, value = line.split(':')
      return value
  raise Exception('Unable to find jiffies from /proc/timer_list')


def GetSystemCommitCharge(meminfo_contents):
  meminfo = _GetProcFileDict(meminfo_contents)
  return (_ConvertKbToByte(meminfo['MemTotal'])
          - _ConvertKbToByte(meminfo['MemFree'])
          - _ConvertKbToByte(meminfo['Buffers'])
          - _ConvertKbToByte(meminfo['Cached']))


def GetCpuStats(stats, add_children=False):
  utime = float(stats[13])
  stime = float(stats[14])
  cutime = float(stats[15])
  cstime = float(stats[16])

  cpu_process_jiffies = utime + stime
  if add_children:
    cpu_process_jiffies += cutime + cstime

  return {'CpuProcessTime': cpu_process_jiffies}


def GetTimestampJiffies(timer_list):
  """Return timestamp of system in jiffies."""
  total_jiffies = float(_GetProcJiffies(timer_list))
  return {'TotalTime': total_jiffies}


def GetMemoryStats(status_contents, stats):
  status = _GetProcFileDict(status_contents)
  if not status or not stats or 'Z' in status['State']:
    return {}
  return {'VM': int(stats[22]),
          'VMPeak': _ConvertKbToByte(status['VmPeak']),
          'WorkingSetSize': int(stats[23]) * resource.getpagesize(),
          'WorkingSetSizePeak': _ConvertKbToByte(status['VmHWM'])}


def GetIOStats(io_contents):
  io = _GetProcFileDict(io_contents)
  return {'ReadOperationCount': int(io['syscr']),
          'WriteOperationCount': int(io['syscw']),
          'ReadTransferCount': int(io['rchar']),
          'WriteTransferCount': int(io['wchar'])}


def GetChildPids(processes, pid):
  child_dict = defaultdict(list)
  for curr_pid, curr_ppid, state in processes:
    if 'Z' in state:
      continue  # Ignore zombie processes
    child_dict[int(curr_ppid)].append(int(curr_pid))
  queue = [pid]
  child_ids = []
  while queue:
    parent = queue.pop()
    if parent in child_dict:
      children = child_dict[parent]
      queue.extend(children)
      child_ids.extend(children)
  return child_ids
