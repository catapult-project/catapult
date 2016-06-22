# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.timeline import atrace_config
from telemetry.timeline import chrome_trace_config


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

  Detailed configurations:
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

    self._atrace_config = atrace_config.AtraceConfig()
    self._chrome_trace_config = chrome_trace_config.ChromeTraceConfig()

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

  @property
  def atrace_config(self):
    return self._atrace_config

  @property
  def chrome_trace_config(self):
    return self._chrome_trace_config


@decorators.Deprecated(2016, 6, 22, 'This class is deprecated. Please use '
                       'atrace_config.AtraceConfig.')
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


@decorators.Deprecated(2016, 6, 22, 'This class is deprecated. Please use '
                       'chrome_trace_config.MemoryDumpConfig.')
class MemoryDumpConfig(object):
  """Stores the triggers for memory dumps in ChromeTraceConfig."""
  def __init__(self):
    self._triggers = []

  def AddTrigger(self, mode, periodic_interval_ms):
    """Adds a new trigger to config.

    Args:
      periodic_interval_ms: Dump time period in milliseconds.
      level_of_detail: Memory dump level of detail string.
          Valid arguments are "background", "light" and "detailed".
    """
    assert mode in ['background', 'light', 'detailed']
    assert periodic_interval_ms > 0
    self._triggers.append({'mode': mode,
                           'periodic_interval_ms': periodic_interval_ms})

  def GetDictForChromeTracing(self):
    """Returns the dump config as dictionary for chrome tracing."""
    # An empty trigger list would mean no periodic memory dumps.
    return {'memory_dump_config': {'triggers': self._triggers}}
