# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import benchmark

class IndependentBenchmark(benchmark.Benchmark):
  @classmethod
  def Name(cls):
    return 'independent'

  @classmethod
  def ShouldTearDownStateAfterEachStoryRun(cls):
    return True


class DependentBenchmark(benchmark.Benchmark):
  @classmethod
  def Name(cls):
    return 'dependent'

  @classmethod
  def ShouldTearDownStateAfterEachStoryRun(cls):
    return False
