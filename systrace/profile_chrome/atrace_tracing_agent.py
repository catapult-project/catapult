# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import py_utils
import threading
import zlib

from devil.utils import cmd_helper

from systrace import trace_result
from systrace import tracing_agents


_ATRACE_OPTIONS = [
    # Compress the trace before sending it over USB.
    '-z',
    # Use a large trace buffer to increase the polling interval.
    '-b', '16384'
]

# Interval in seconds for sampling atrace data.
_ATRACE_INTERVAL = 15

# If a custom list of categories is not specified, traces will include
# these categories (if available on the device).
_DEFAULT_CATEGORIES = 'sched gfx view dalvik webview input disk am wm'.split()

_TRACING_ON_PATH = '/sys/kernel/debug/tracing/tracing_on'


class AtraceAgent(tracing_agents.TracingAgent):
  def __init__(self, device, ring_buffer):
    tracing_agents.TracingAgent.__init__(self)
    self._device = device
    self._ring_buffer = ring_buffer
    self._done = threading.Event()
    self._thread = None
    self._trace_data = None
    self._categories = None

  def __repr__(self):
    return 'atrace'

  @staticmethod
  def GetCategories(device):
    return device.RunShellCommand('atrace --list_categories')

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StartAgentTracing(self, config, timeout=None):
    self._categories = _ComputeAtraceCategories(config)
    self._thread = threading.Thread(target=self._CollectData)
    self._thread.start()
    return True

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StopAgentTracing(self, timeout=None):
    self._done.set()
    return True

  @py_utils.Timeout(tracing_agents.GET_RESULTS_TIMEOUT)
  def GetResults(self, timeout=None):
    self._thread.join()
    self._thread = None
    return trace_result.TraceResult('systemTraceEvents', self._trace_data)

  def SupportsExplicitClockSync(self):
    return False

  def RecordClockSyncMarker(self, sync_id, did_record_sync_marker_callback):
    # pylint: disable=unused-argument
    assert self.SupportsExplicitClockSync(), ('Clock sync marker cannot be '
        'recorded since explicit clock sync is not supported.')

  def IsTracingOn(self):
    result = self._RunAdbShellCommand(['cat', _TRACING_ON_PATH])
    return result.strip() == '1'

  def _RunAdbShellCommand(self, command):
    # We use a separate interface to adb because the one from AndroidCommands
    # isn't re-entrant.
    # TODO(jbudorick) Look at providing a way to unhandroll this once the
    #                 adb rewrite has fully landed.
    device_param = (['-s', str(self._device)] if str(self._device) else [])
    cmd = ['adb'] + device_param + ['shell'] + command
    return cmd_helper.GetCmdOutput(cmd)

  def _RunATraceCommand(self, command):
    cmd = ['atrace', '--%s' % command] + _ATRACE_OPTIONS + self._categories
    return self._RunAdbShellCommand(cmd)

  def _ForceStopAtrace(self):
    # atrace on pre-M Android devices cannot be stopped asynchronously
    # correctly. Use synchronous mode to force stop.
    cmd = ['atrace', '-t', '0']
    return self._RunAdbShellCommand(cmd)

  def _CollectData(self):
    trace_data = []
    self._RunATraceCommand('async_start')
    try:
      while not self._done.is_set():
        self._done.wait(_ATRACE_INTERVAL)
        if not self._ring_buffer or self._done.is_set():
          trace_data.append(
              self._DecodeTraceData(self._RunATraceCommand('async_dump')))
    finally:
      trace_data.append(
          self._DecodeTraceData(self._RunATraceCommand('async_stop')))
      if self.IsTracingOn():
        self._ForceStopAtrace()
    self._trace_data = ''.join([zlib.decompress(d) for d in trace_data])

  @staticmethod
  def _DecodeTraceData(trace_data):
    try:
      trace_start = trace_data.index('TRACE:')
    except ValueError:
      raise RuntimeError('Atrace start marker not found')
    trace_data = trace_data[trace_start + 6:]

    # Collapse CRLFs that are added by adb shell.
    if trace_data.startswith('\r\n'):
      trace_data = trace_data.replace('\r\n', '\n')

    # Skip the initial newline.
    return trace_data[1:]


class AtraceConfig(tracing_agents.TracingConfig):
  def __init__(self, atrace_categories, device, ring_buffer):
    tracing_agents.TracingConfig.__init__(self)
    self.atrace_categories = atrace_categories
    self.device = device
    self.ring_buffer = ring_buffer


def try_create_agent(config):
  if config.atrace_categories:
    return AtraceAgent(config.device, config.ring_buffer)
  return None

def add_options(parser):
  atrace_opts = optparse.OptionGroup(parser, 'Atrace tracing options')
  atrace_opts.add_option('-s', '--systrace', help='Capture a systrace with '
                           'the chosen comma-delimited systrace categories. You'
                           ' can also capture a combined Chrome + systrace by '
                           'enabling both types of categories. Use "list" to '
                           'see the available categories. Systrace is disabled'
                           ' by default. Note that in this case, Systrace is '
                           'synonymous with Atrace.',
                           metavar='ATRACE_CATEGORIES',
                           dest='atrace_categories', default='')
  return atrace_opts

def get_config(options):
  return AtraceConfig(options.atrace_categories, options.device,
                      options.ring_buffer)

def _ComputeAtraceCategories(config):
  if not config.atrace_categories:
    return _DEFAULT_CATEGORIES
  return config.atrace_categories.split(',')
