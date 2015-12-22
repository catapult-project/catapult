# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json


class TracingConfig(object):
  """Tracing config is the configuration for Chrome tracing.

  This produces the trace config JSON string for Chrome tracing. For the details
  about the JSON string format, see base/trace_event/trace_config.h.
  """
  def __init__(self, tracing_options, tracing_category_filter):
    self._tracing_options = tracing_options
    self._tracing_category_filter = tracing_category_filter

  @property
  def tracing_options(self):
    return self._tracing_options

  @property
  def tracing_category_filter(self):
    return self._tracing_category_filter

  def GetTraceConfigJsonString(self):
    result = {}
    result.update(self._tracing_options.GetDictForChromeTracing())
    result.update(self._tracing_category_filter.GetDictForChromeTracing())
    return json.dumps(result, sort_keys=True)
