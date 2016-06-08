# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry.timeline import tracing_category_filter

RECORD_MODE_PARAM = 'record_mode'
ENABLE_SYSTRACE_PARAM = 'enable_systrace'

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

def ConvertStringToCamelCase(string):
  """Convert an underscore/hyphen-case string to its camel-case counterpart.

  This function is the inverse of Chromium's ConvertFromCamelCase function
  in src/content/browser/devtools/protocol/tracing_handler.cc.
  """
  parts = re.split(r'[-_]', string)
  return parts[0] + ''.join([p.title() for p in parts[1:]])


def ConvertDictKeysToCamelCaseRecursively(data):
  """Recursively convert dictionary keys from underscore/hyphen- to camel-case.

  This function is the inverse of Chromium's ConvertDictKeyStyle function
  in src/content/browser/devtools/protocol/tracing_handler.cc.
  """
  if isinstance(data, dict):
    return {ConvertStringToCamelCase(k):
            ConvertDictKeysToCamelCaseRecursively(v)
            for k, v in data.iteritems()}
  elif isinstance(data, list):
    return map(ConvertDictKeysToCamelCaseRecursively, data)
  else:
    return data


class TracingConfig(object):
  """Tracing config is the configuration for tracing in Telemetry.

  TracingConfig configures tracing in Telemetry. It contains tracing options
  that control which core tracing system should be enabled. If a tracing
  system requires additional configuration, e.g., what to trace, then it is
  typically configured in its own config class. TracingConfig provides
  interfaces to access the configuration for those tracing systems.

  Options:
      enable_atrace_trace: a boolean that specifies whether to enable
          atrace tracing.
      enable_chrome_trace: a boolean that specifies whether to enable
          chrome tracing.
      enable_platform_display_trace: a boolean that specifies whether to
          platform display tracing.
      enable_android_graphics_memtrack: a boolean that specifies whether
          to enable the memtrack_helper daemon to track graphics memory on
          Android (see goo.gl/4Y30p9). Doesn't have any effects on other OSs.
      enable_battor_trace: a boolean that specifies whether to enable BattOr
          tracing.
      atrace_config: Stores configuration options specific to Atrace.
      chrome_trace_config: Stores configuration options specific to
          Chrome trace.
  """

  def __init__(self):
    self._enable_atrace_trace = False
    self._enable_platform_display_trace = False
    self._enable_android_graphics_memtrack = False
    self._enable_battor_trace = False
    self._enable_chrome_trace = False
    self._atrace_config = AtraceConfig()
    self._chrome_trace_config = ChromeTraceConfig()

  @property
  def tracing_category_filter(self):
    return self._chrome_trace_config.tracing_category_filter

  def SetNoOverheadFilter(self):
    self._chrome_trace_config.SetNoOverheadFilter()

  def SetMinimalOverheadFilter(self):
    self._chrome_trace_config.SetMinimalOverheadFilter()

  def SetDebugOverheadFilter(self):
    self._chrome_trace_config.SetDebugOverheadFilter()

  def SetTracingCategoryFilter(self, cf):
    self._chrome_trace_config.SetTracingCategoryFilter(cf)

  def SetMemoryDumpConfig(self, dump_config):
    self._chrome_trace_config.SetMemoryDumpConfig(dump_config)

  @property
  def atrace_config(self):
    return self._atrace_config

  @property
  def enable_atrace_trace(self):
    return self._enable_atrace_trace

  @enable_atrace_trace.setter
  def enable_atrace_trace(self, value):
    if value:
      assert not self._chrome_trace_config.enable_systrace, (
          "Cannot enable atrace while Chrome systrace is already enabled.")
    self._enable_atrace_trace = value

  @property
  def enable_platform_display_trace(self):
    return self._enable_platform_display_trace

  @enable_platform_display_trace.setter
  def enable_platform_display_trace(self, value):
    self._enable_platform_display_trace = value

  @property
  def enable_android_graphics_memtrack(self):
    return self._enable_android_graphics_memtrack

  @enable_android_graphics_memtrack.setter
  def enable_android_graphics_memtrack(self, value):
    self._enable_android_graphics_memtrack = value

  @property
  def enable_battor_trace(self):
    return self._enable_battor_trace

  @enable_battor_trace.setter
  def enable_battor_trace(self, value):
    self._enable_battor_trace = value

  @property
  def enable_chrome_trace(self):
    return self._enable_chrome_trace

  @enable_chrome_trace.setter
  def enable_chrome_trace(self, value):
    self._enable_chrome_trace = value

  # Chrome Trace Options
  @property
  def record_mode(self):
    return self._chrome_trace_config.record_mode

  @record_mode.setter
  def record_mode(self, value):
    self._chrome_trace_config.record_mode = value

  @property
  def enable_systrace(self):
    return self._chrome_trace_config.enable_systrace

  @enable_systrace.setter
  def enable_systrace(self, value):
    if value:
      assert not self._enable_atrace_trace, (
        "Cannot enable Chrome systrace while atrace is already enabled.")
    self._chrome_trace_config.enable_systrace = value

  def GetChromeTraceConfigForStartupTracing(self):
    return self._chrome_trace_config.GetChromeTraceConfigForStartupTracing()

  @property
  def requires_modern_devtools_tracing_start_api(self):
    return self._chrome_trace_config.requires_modern_devtools_tracing_start_api

  def GetChromeTraceConfigForDevTools(self):
    return self._chrome_trace_config.GetChromeTraceConfigForDevTools()

  def GetChromeTraceCategoriesAndOptionsForDevTools(self):
    return (self._chrome_trace_config.
        GetChromeTraceCategoriesAndOptionsForDevTools())


class AtraceConfig(object):
  """Stores configuration options specific to Atrace.

    categories: List that specifies the Atrace categories to trace.
        Example: ['sched', 'webview']
    app_name: String or list that specifies the application name (or names)
        on which to run application level tracing.
        Example: 'org.chromium.webview_shell'
  """
  def __init__(self):
    self.categories = None
    self.app_name = None


class ChromeTraceConfig(object):
  """Stores configuration options specific to the Chrome tracing agent.

    This produces the trace config JSON string for tracing in Chrome.

    record_mode: can be any mode in RECORD_MODE_MAP. This corresponds to
        record modes in chrome.
    enable_systrace: a boolean that specifies whether to enable systrace.
    tracing_category_filter: Object that specifies which tracing
        categories to trace.
    memory_dump_config: Stores the triggers for memory dumps.

  """

  def __init__(self):
    self._record_mode = RECORD_AS_MUCH_AS_POSSIBLE
    self._enable_systrace = False
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter())
    self._memory_dump_config = None

  @property
  def tracing_category_filter(self):
    return self._tracing_category_filter

  def SetNoOverheadFilter(self):
    self._tracing_category_filter = (
        tracing_category_filter.CreateNoOverheadFilter())

  def SetMinimalOverheadFilter(self):
    self._tracing_category_filter = (
        tracing_category_filter.CreateMinimalOverheadFilter())

  def SetDebugOverheadFilter(self):
    self._tracing_category_filter = (
        tracing_category_filter.CreateDebugOverheadFilter())

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

  def GetChromeTraceConfigForStartupTracing(self):
    """Map the config to a JSON string for startup tracing.

    All keys in the returned dictionary use underscore-case (e.g.
    'enable_systrace'). In addition, the 'record_mode' value uses hyphen-case
    (e.g. 'record-until-full').
    """
    result = {
        RECORD_MODE_PARAM: RECORD_MODE_MAP[self._record_mode],
        ENABLE_SYSTRACE_PARAM: self._enable_systrace
    }
    result.update(self._tracing_category_filter.GetDictForChromeTracing())
    if self._memory_dump_config:
      result.update(self._memory_dump_config.GetDictForChromeTracing())
    return result

  @property
  def requires_modern_devtools_tracing_start_api(self):
    """Returns True iff the config CANNOT be passed via the legacy DevTools API.

    Legacy DevTools Tracing.start API:
      Available since:    the introduction of the Tracing.start request.
      Parameters:         categories (string), options (string),
                          bufferUsageReportingInterval (number),
                          transferMode (enum).
      TraceConfig method: GetChromeTraceCategoriesAndOptionsStringsForDevTools()

    Modern DevTools Tracing.start API:
      Available since:    Chrome 51.0.2683.0.
      Parameters:         traceConfig (dict),
                          bufferUsageReportingInterval (number),
                          transferMode (enum).
      TraceConfig method: GetChromeTraceConfigDictForDevTools()
    """
    # Memory dump config cannot be passed via the 'options' string (legacy API)
    # in the DevTools Tracing.start request.
    return bool(self._memory_dump_config)

  def GetChromeTraceConfigForDevTools(self):
    """Map the config to a DevTools API config dictionary.

    All keys in the returned dictionary use camel-case (e.g. 'enableSystrace').
    In addition, the 'recordMode' value also uses camel-case (e.g.
    'recordUntilFull'). This is to invert the camel-case ->
    underscore/hyphen-delimited mapping performed in Chromium devtools.
    """
    result = self.GetChromeTraceConfigForStartupTracing()
    if result[RECORD_MODE_PARAM]:
      result[RECORD_MODE_PARAM] = ConvertStringToCamelCase(
          result[RECORD_MODE_PARAM])
    return ConvertDictKeysToCamelCaseRecursively(result)

  def GetChromeTraceCategoriesAndOptionsForDevTools(self):
    """Map the categories and options to their DevTools API counterparts."""
    assert not self.requires_modern_devtools_tracing_start_api
    options_parts = [RECORD_MODE_MAP[self._record_mode]]
    if self._enable_systrace:
      options_parts.append(ENABLE_SYSTRACE)
    return (self._tracing_category_filter.stable_filter_string,
            ','.join(options_parts))


class MemoryDumpConfig(object):
  """Stores the triggers for memory dumps in ChromeTraceConfig."""
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
