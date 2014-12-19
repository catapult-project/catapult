# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TracingController(object):
  def __init__(self, tracing_controller_backend):
    """Provides control of the tracing systems supported by telemetry."""
    self._tracing_controller_backend = tracing_controller_backend

  def Start(self, trace_options, category_filter, timeout=10):
    """Starts tracing.

    trace_options specifies which tracing systems to activate. Category filter
    allows fine-tuning of the data that are collected by the selected tracing
    systems.

    Some tracers are process-specific, e.g. chrome tracing, but are not
    guaranteed to be supported. In order to support tracing of these kinds of
    tracers, Start will succeed *always*, even if the tracing systems you have
    requested are not supported.

    If you absolutely require a particular tracer to exist, then check
    for its support after you have started the process in question. Or, have
    your code fail gracefully when the data you require is not present in the
    resulting trace.
    """
    self._tracing_controller_backend.Start(
        trace_options, category_filter, timeout)

  def Stop(self):
    """Stops tracing and returns a TraceValue."""
    return self._tracing_controller_backend.Stop()

  @property
  def is_tracing_running(self):
    return self._tracing_controller_backend.is_tracing_running

  def IsChromeTracingSupported(self):
    """Returns whether chrome tracing is supported."""
    return self._tracing_controller_backend.IsChromeTracingSupported()
