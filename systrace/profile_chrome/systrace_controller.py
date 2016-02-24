# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import threading
import zlib

from devil.utils import cmd_helper

from profile_chrome import controllers
from profile_chrome import util


_SYSTRACE_OPTIONS = [
    # Compress the trace before sending it over USB.
    '-z',
    # Use a large trace buffer to increase the polling interval.
    '-b', '16384'
]

# Interval in seconds for sampling systrace data.
_SYSTRACE_INTERVAL = 15

_TRACING_ON_PATH = '/sys/kernel/debug/tracing/tracing_on'


class SystraceController(controllers.BaseController):
  def __init__(self, device, categories, ring_buffer):
    controllers.BaseController.__init__(self)
    self._device = device
    self._categories = categories
    self._ring_buffer = ring_buffer
    self._done = threading.Event()
    self._thread = None
    self._trace_data = None

  def __repr__(self):
    return 'systrace'

  @staticmethod
  def GetCategories(device):
    return device.RunShellCommand('atrace --list_categories')

  def StartTracing(self, _):
    self._thread = threading.Thread(target=self._CollectData)
    self._thread.start()

  def StopTracing(self):
    self._done.set()

  def PullTrace(self):
    self._thread.join()
    self._thread = None
    if self._trace_data:
      output_name = 'systrace-%s' % util.GetTraceTimestamp()
      with open(output_name, 'w') as out:
        out.write(self._trace_data)
      return output_name

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
    cmd = ['atrace', '--%s' % command] + _SYSTRACE_OPTIONS + self._categories
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
        self._done.wait(_SYSTRACE_INTERVAL)
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
      raise RuntimeError('Systrace start marker not found')
    trace_data = trace_data[trace_start + 6:]

    # Collapse CRLFs that are added by adb shell.
    if trace_data.startswith('\r\n'):
      trace_data = trace_data.replace('\r\n', '\n')

    # Skip the initial newline.
    return trace_data[1:]
