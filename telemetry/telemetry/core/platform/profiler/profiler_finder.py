# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform.profiler import perf_profiler


_PROFILERS = [perf_profiler.PerfProfiler]


def FindProfiler(name):
  for profiler in _PROFILERS:
    if profiler.name() == name:
      return profiler
  return None


def GetAllAvailableProfilers():
  return [p.name() for p in _PROFILERS]
