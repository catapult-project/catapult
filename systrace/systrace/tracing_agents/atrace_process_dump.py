# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Tracing agent that captures periodic per-process memory dumps and other
# useful information from ProcFS like utime, stime, OOM stats, etc.

import logging
import optparse
import py_utils

from devil.android import device_utils
from devil.android.device_errors import AdbShellCommandFailedError
from systrace import tracing_agents
from systrace import trace_result

TRACE_HEADER = 'ATRACE_PROCESS_DUMP'
TRACE_RESULT_NAME = 'atraceProcessDump'

HELPER_COMMAND = '/data/local/tmp/atrace_helper'
HELPER_STOP_COMMAND = 'kill -TERM `pidof atrace_helper`'
HELPER_DUMP_JSON = '/data/local/tmp/procdump.json'


class AtraceProcessDumpAgent(tracing_agents.TracingAgent):
  def __init__(self):
    super(AtraceProcessDumpAgent, self).__init__()
    self._device = None
    self._dump = None

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StartAgentTracing(self, config, timeout=None):
    self._device = device_utils.DeviceUtils(config.device_serial_number)
    cmd = [HELPER_COMMAND, '-b', '-g',
        '-t', str(config.dump_interval_ms),
        '-o', HELPER_DUMP_JSON]
    self._device.RunShellCommand(cmd, check_return=True, as_root=True)
    return True

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StopAgentTracing(self, timeout=None):
    self._device.RunShellCommand(
        HELPER_STOP_COMMAND,
        shell=True, check_return=True, as_root=True)
    try:
      self._device.RunShellCommand(['test', '-f', HELPER_DUMP_JSON],
          check_return=True, as_root=True)
      self._dump = self._device.ReadFile(HELPER_DUMP_JSON, force_pull=True)
      self._device.RunShellCommand(['rm', HELPER_DUMP_JSON],
          check_return=True, as_root=True)
    except AdbShellCommandFailedError:
      logging.error('AtraceProcessDumpAgent failed to pull data. Check device storage.')
      return False
    return True

  @py_utils.Timeout(tracing_agents.GET_RESULTS_TIMEOUT)
  def GetResults(self, timeout=None):
    result = TRACE_HEADER + '\n' + self._dump
    return trace_result.TraceResult(TRACE_RESULT_NAME, result)

  def SupportsExplicitClockSync(self):
    return False

  def RecordClockSyncMarker(self, sync_id, did_record_sync_marker_callback):
    pass


class AtraceProcessDumpConfig(tracing_agents.TracingConfig):
  def __init__(self, enabled, device_serial_number, dump_interval_ms):
    tracing_agents.TracingConfig.__init__(self)
    self.enabled = enabled
    self.device_serial_number = device_serial_number
    self.dump_interval_ms = dump_interval_ms


def add_options(parser):
  options = optparse.OptionGroup(parser, 'Atrace process dump options')
  options.add_option('--process-dump-interval', dest='process_dump_interval_ms',
                     default=5000,
                     help='Interval between memory dumps in milliseconds.')
  options.add_option('--process-dump', dest='process_dump_enable',
                     default=False, action='store_true',
                     help='Capture periodic per-process memory dumps.')
  return options


def get_config(options):
  can_enable = (options.target == 'android') and (not options.from_file)
  return AtraceProcessDumpConfig(
    enabled=(options.process_dump_enable and can_enable),
    device_serial_number=options.device_serial_number,
    dump_interval_ms=options.process_dump_interval_ms,
  )


def try_create_agent(config):
  if config.enabled:
    return AtraceProcessDumpAgent()
  return None
