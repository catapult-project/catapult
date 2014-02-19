# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs

from telemetry.core.platform import profiler


class TraceProfiler(profiler.Profiler):

  def __init__(self, browser_backend, platform_backend, output_path, state,
               categories=None):
    super(TraceProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)
    assert self._browser_backend.supports_tracing
    # We always want flow events when tracing via telemetry.
    categories_with_flow = 'disabled-by-default-toplevel.flow'
    if categories:
      categories_with_flow = ',%s' % categories
    self._browser_backend.StartTracing(categories_with_flow, timeout=10)

  @classmethod
  def name(cls):
    return 'trace'

  @classmethod
  def is_supported(cls, browser_type):
    return True

  def CollectProfile(self):
    print 'Processing trace...'

    trace_result = self._browser_backend.StopTracing()

    trace_file = '%s.json' % self._output_path

    with codecs.open(trace_file, 'w', encoding='utf-8') as f:
      trace_result.Serialize(f)

    print 'Trace saved as %s' % trace_file
    print 'To view, open in chrome://tracing'

    return [trace_file]


class TraceDetailedProfiler(TraceProfiler):

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(TraceDetailedProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state,
        categories='disabled-by-default-cc.debug*')

  @classmethod
  def name(cls):
    return 'trace-detailed'


class TraceAllProfiler(TraceProfiler):

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(TraceAllProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state,
        categories='disabled-by-default-*')

  @classmethod
  def name(cls):
    return 'trace-all'
