# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from telemetry.core.platform import posix_platform_backend


class LinuxPlatformBackend(posix_platform_backend.PosixPlatformBackend):

  def StartRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def GetRawDisplayFrameRateMeasurements(self):
    raise NotImplementedError()

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def _GetProcFileDict(self, filename):
    retval = {}
    for line in self._GetFileContents(filename).splitlines():
      key, value = line.split(':')
      retval[key.strip()] = value.strip()
    return retval

  def _ConvertKbToByte(self, value):
    return int(value.replace('kB','')) * 1024

  def GetSystemCommitCharge(self):
    meminfo = self._GetProcFileDict('/proc/meminfo')
    return (self._ConvertKbToByte(meminfo['MemTotal'])
            - self._ConvertKbToByte(meminfo['MemFree'])
            - self._ConvertKbToByte(meminfo['Buffers'])
            - self._ConvertKbToByte(meminfo['Cached']))

  def GetMemoryStats(self, pid):
    status = self._GetProcFileDict('/proc/%s/status' % pid)
    stats = self._GetFileContents('/proc/%s/stat' % pid).split()

    if not status or not stats or 'Z' in status['State']:
      return {}
    return {'VM': int(stats[22]),
            'VMPeak': self._ConvertKbToByte(status['VmPeak']),
            'WorkingSetSize': int(stats[23]) * resource.getpagesize(),
            'WorkingSetSizePeak': self._ConvertKbToByte(status['VmHWM'])}

  def GetIOStats(self, pid):
    io = self._GetProcFileDict('/proc/%s/io' % pid)
    return {'ReadOperationCount': int(io['syscr']),
            'WriteOperationCount': int(io['syscw']),
            'ReadTransferCount': int(io['rchar']),
            'WriteTransferCount': int(io['wchar'])}

  def GetOSName(self):
    return 'linux'
