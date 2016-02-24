# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import re
import time

from profile_chrome import controllers

from devil.android import device_errors
from devil.android.sdk import intent


_HEAP_PROFILE_MMAP_PROPERTY = 'heapprof.mmap'

class ChromeTracingController(controllers.BaseController):
  def __init__(self, device, package_info,
               categories, ring_buffer, trace_memory=False):
    controllers.BaseController.__init__(self)
    self._device = device
    self._package_info = package_info
    self._categories = categories
    self._ring_buffer = ring_buffer
    self._logcat_monitor = self._device.GetLogcatMonitor()
    self._trace_file = None
    self._trace_interval = None
    self._trace_memory = trace_memory
    self._is_tracing = False
    self._trace_start_re = \
       re.compile(r'Logging performance trace to file')
    self._trace_finish_re = \
       re.compile(r'Profiler finished[.] Results are in (.*)[.]')

  def __repr__(self):
    return 'chrome trace'

  @staticmethod
  def GetCategories(device, package_info):
    with device.GetLogcatMonitor() as logmon:
      device.BroadcastIntent(intent.Intent(
          action='%s.GPU_PROFILER_LIST_CATEGORIES' % package_info.package))
      try:
        json_category_list = logmon.WaitFor(
            re.compile(r'{"traceCategoriesList(.*)'), timeout=5).group(0)
      except device_errors.CommandTimeoutError:
        raise RuntimeError('Performance trace category list marker not found. '
                           'Is the correct version of the browser running?')

    record_categories = set()
    disabled_by_default_categories = set()
    json_data = json.loads(json_category_list)['traceCategoriesList']
    for item in json_data:
      for category in item.split(','):
        if category.startswith('disabled-by-default'):
          disabled_by_default_categories.add(category)
        else:
          record_categories.add(category)

    return list(record_categories), list(disabled_by_default_categories)

  def StartTracing(self, interval):
    self._trace_interval = interval
    self._logcat_monitor.Start()
    start_extras = {'categories': ','.join(self._categories)}
    if self._ring_buffer:
      start_extras['continuous'] = None
    self._device.BroadcastIntent(intent.Intent(
        action='%s.GPU_PROFILER_START' % self._package_info.package,
        extras=start_extras))

    if self._trace_memory:
      self._device.EnableRoot()
      self._device.SetProp(_HEAP_PROFILE_MMAP_PROPERTY, 1)

    # Chrome logs two different messages related to tracing:
    #
    # 1. "Logging performance trace to file"
    # 2. "Profiler finished. Results are in [...]"
    #
    # The first one is printed when tracing starts and the second one indicates
    # that the trace file is ready to be pulled.
    try:
      self._logcat_monitor.WaitFor(self._trace_start_re, timeout=5)
      self._is_tracing = True
    except device_errors.CommandTimeoutError:
      raise RuntimeError(
          'Trace start marker not found. Possible causes: 1) Is the correct '
          'version of the browser running? 2) Is the browser already launched?')

  def StopTracing(self):
    if self._is_tracing:
      self._device.BroadcastIntent(intent.Intent(
          action='%s.GPU_PROFILER_STOP' % self._package_info.package))
      self._trace_file = self._logcat_monitor.WaitFor(
          self._trace_finish_re, timeout=120).group(1)
      self._is_tracing = False
    if self._trace_memory:
      self._device.SetProp(_HEAP_PROFILE_MMAP_PROPERTY, 0)

  def PullTrace(self):
    # Wait a bit for the browser to finish writing the trace file.
    time.sleep(self._trace_interval / 4 + 1)

    trace_file = self._trace_file.replace('/storage/emulated/0/', '/sdcard/')
    host_file = os.path.join(os.path.curdir, os.path.basename(trace_file))
    try:
      self._device.PullFile(trace_file, host_file)
    except device_errors.AdbCommandFailedError:
      raise RuntimeError(
          'Cannot pull the trace file. Have you granted Storage permission to '
          'the browser? (Android Settings -> Apps -> [the browser app] -> '
          'Permissions -> Storage)')
    return host_file
