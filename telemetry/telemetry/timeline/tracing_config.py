# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.timeline import tracing_category_filter

ECHO_TO_CONSOLE = 'trace-to-console'
ENABLE_SYSTRACE = 'enable-systrace'
RECORD_AS_MUCH_AS_POSSIBLE = 'record-as-much-as-possible'
RECORD_CONTINUOUSLY = 'record-continuously'
RECORD_UNTIL_FULL = 'record-until-full'

# Map telemetry's tracing record_mode to the DevTools API string.
# (The keys happen to be the same as the values.)
RECORD_MODE_MAP = {
  RECORD_UNTIL_FULL: 'record-until-full',
  RECORD_CONTINUOUSLY: 'record-continuously',
  RECORD_AS_MUCH_AS_POSSIBLE: 'record-as-much-as-possible',
  ECHO_TO_CONSOLE: 'trace-to-console'
}


class MemoryDumpConfig(object):
  """Stores the triggers for memory dumps in tracing config."""
  def __init__(self):
    self._triggers = []

  def AddTrigger(self, mode, periodic_interval_ms):
    """Adds a new trigger to config.

    Args:
      periodic_interval_ms: Dump time period in milliseconds.
      level_of_detail: Memory dump level of detail string.
          Valid arguments are "light" and "detailed".
    """
    assert mode in ['light', 'detailed']
    assert periodic_interval_ms > 0
    self._triggers.append({'mode': mode,
                           'periodic_interval_ms': periodic_interval_ms})

  def GetDictForChromeTracing(self):
    """Returns the dump config as dictionary for chrome tracing."""
    # An empty trigger list would mean no periodic memory dumps.
    return {'memory_dump_config': {'triggers': self._triggers}}


class TracingConfig(object):
  """Tracing config is the configuration for Chrome tracing.

  This produces the trace config JSON string for Chrome tracing. For the details
  about the JSON string format, see base/trace_event/trace_config.h.

  Contains tracing options:
  Tracing options control which core tracing systems should be enabled.

  This simply turns on those systems. If those systems have additional options,
  e.g. what to trace, then they are typically configured by adding
  categories to the TracingCategoryFilter.

  Options:
      enable_chrome_trace: a boolean that specifies whether to enable
          chrome tracing.
      enable_platform_display_trace: a boolean that specifies whether to
          platform display tracing.
      enable_android_graphics_memtrack: a boolean that specifies whether
          to enable the memtrack_helper daemon to track graphics memory on
          Android (see goo.gl/4Y30p9). Doesn't have any effects on other OSs.

      The following ones are specific to chrome tracing. See
      base/trace_event/trace_config.h for more information.
          record_mode: can be any mode in RECORD_MODE_MAP. This corresponds to
                       record modes in chrome.
          enable_systrace: a boolean that specifies whether to enable systrace.

  """

  def __init__(self):
    # Trace options.
    self.enable_chrome_trace = False
    self.enable_platform_display_trace = False
    self.enable_android_graphics_memtrack = False
    self._record_mode = RECORD_AS_MUCH_AS_POSSIBLE
    self._enable_systrace = False
    # Tracing category filter.
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter())
    self._memory_dump_config = None

  @property
  def tracing_category_filter(self):
    return self._tracing_category_filter

  def GetChromeTraceConfigJsonString(self):
    result = {}
    result.update(self.GetDictForChromeTracing())
    result.update(self._tracing_category_filter.GetDictForChromeTracing())
    if self._memory_dump_config:
      result.update(self._memory_dump_config.GetDictForChromeTracing())
    return json.dumps(result, sort_keys=True)

  def SetNoOverheadFilter(self):
    """Sets a filter with the least overhead possible.

    This contains no sub-traces of thread tasks, so it's only useful for
    capturing the cpu-time spent on threads (as well as needed benchmark
    traces).

    FIXME: Remove webkit.console when blink.console lands in chromium and
    the ref builds are updated. crbug.com/386847
    """
    categories = [
      "toplevel",
      "benchmark",
      "webkit.console",
      "blink.console",
      "trace_event_overhead"
    ]
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter(
            filter_string=','.join(categories)))

  def SetMinimalOverheadFilter(self):
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter(filter_string=''))

  def SetDebugOverheadFilter(self):
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter(
            filter_string='*,disabled-by-default-cc.debug'))

  def SetTracingCategoryFilter(self, cf):
    if isinstance(cf, tracing_category_filter.TracingCategoryFilter):
      self._tracing_category_filter = cf
    else:
      raise TypeError(
          'Must pass SetTracingCategoryFilter a TracingCategoryFilter instance')

  def SetMemoryDumpConfig(self, dump_config):
    if isinstance(dump_config, MemoryDumpConfig):
      self._memory_dump_config = dump_config
    else:
      raise TypeError(
          'Must pass SetMemoryDumpConfig a MemoryDumpConfig instance')

  # Trace Options
  @property
  def record_mode(self):
    return self._record_mode

  @record_mode.setter
  def record_mode(self, value):
    assert value in RECORD_MODE_MAP
    self._record_mode = value

  @property
  def enable_systrace(self):
    return self._enable_systrace

  @enable_systrace.setter
  def enable_systrace(self, value):
    self._enable_systrace = value

  def GetTraceOptionsStringForChromeDevtool(self):
    """Map Chrome tracing options in Telemetry to the DevTools API string."""
    result = [RECORD_MODE_MAP[self._record_mode]]
    if self._enable_systrace:
      result.append(ENABLE_SYSTRACE)
    return ','.join(result)

  def GetDictForChromeTracing(self):
    RECORD_MODE_PARAM = 'record_mode'
    ENABLE_SYSTRACE_PARAM = 'enable_systrace'

    result = {}
    result[RECORD_MODE_PARAM] = (
        RECORD_MODE_MAP[self._record_mode])
    if self._enable_systrace:
      result[ENABLE_SYSTRACE_PARAM] = True
    return result
