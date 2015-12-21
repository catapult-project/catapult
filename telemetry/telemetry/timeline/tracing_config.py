# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options


class TracingConfig(object):
  """Tracing config is the configuration for Chrome tracing.

  This produces the trace config JSON string for Chrome tracing. For the details
  about the JSON string format, see base/trace_event/trace_config.h.
  """
  def __init__(self):
    self._tracing_options = tracing_options.TracingOptions()
    self._tracing_category_filter = (
        tracing_category_filter.TracingCategoryFilter())

  @property
  def tracing_options(self):
    return self._tracing_options

  @property
  def tracing_category_filter(self):
    return self._tracing_category_filter

  def GetChromeTraceConfigJsonString(self):
    result = {}
    result.update(self._tracing_options.GetDictForChromeTracing())
    result.update(self._tracing_category_filter.GetDictForChromeTracing())
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
