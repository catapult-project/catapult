# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

RECORD_UNTIL_FULL = 'record-until-full'
RECORD_CONTINUOUSLY = 'record-continuously'
RECORD_AS_MUCH_AS_POSSIBLE = 'record-as-much-as-possible'
ECHO_TO_CONSOLE = 'trace-to-console'

RECORD_MODES = [
  RECORD_UNTIL_FULL,
  RECORD_CONTINUOUSLY,
  RECORD_AS_MUCH_AS_POSSIBLE,
  ECHO_TO_CONSOLE
]

ENABLE_SYSTRACE = 'enable-systrace'

class TracingOptions(object):
  """Tracing options control which core tracing systems should be enabled.

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
          record_mode: can be any mode in RECORD_MODES. This corresponds to
                       record modes in chrome.
          enable_systrace: a boolean that specifies whether to enable systrace.
  """
  # Map telemetry's tracing record_mode to the DevTools API string.
  # (The keys happen to be the same as the values.)
  _RECORD_MODE_MAP = {
    RECORD_UNTIL_FULL: 'record-until-full',
    RECORD_CONTINUOUSLY: 'record-continuously',
    RECORD_AS_MUCH_AS_POSSIBLE: 'record-as-much-as-possible',
    ECHO_TO_CONSOLE: 'trace-to-console'
  }

  def __init__(self):
    self.enable_chrome_trace = False
    self.enable_platform_display_trace = False
    self.enable_android_graphics_memtrack = False

    self._record_mode = RECORD_AS_MUCH_AS_POSSIBLE
    self._enable_systrace = False

  @property
  def record_mode(self):
    return self._record_mode

  @record_mode.setter
  def record_mode(self, value):
    assert value in RECORD_MODES
    self._record_mode = value

  @property
  def enable_systrace(self):
    return self._enable_systrace

  @enable_systrace.setter
  def enable_systrace(self, value):
    self._enable_systrace = value

  def GetTraceOptionsStringForChromeDevtool(self):
    """Map Chrome tracing options in Telemetry to the DevTools API string."""
    result = [TracingOptions._RECORD_MODE_MAP[self._record_mode]]
    if self._enable_systrace:
      result.append(ENABLE_SYSTRACE)
    return ','.join(result)

  def GetDictForChromeTracing(self):
    RECORD_MODE_PARAM = 'record_mode'
    ENABLE_SYSTRACE_PARAM = 'enable_systrace'

    result = {}
    result[RECORD_MODE_PARAM] = (
        TracingOptions._RECORD_MODE_MAP[self._record_mode])
    if self._enable_systrace:
      result[ENABLE_SYSTRACE_PARAM] = True
    return result
