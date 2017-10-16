# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry import benchmark_runner
from telemetry.story import expectations
from telemetry.testing import stream
import mock


class DisabledExpectation(expectations.StoryExpectations):
  def SetExpectations(self):
    self.DisableBenchmark([expectations.ALL], 'crbug.com/123')


class BenchmarkEnabled(benchmark.Benchmark):
  """ Enabled benchmark for testing."""

  @classmethod
  def Name(cls):
    return 'EnabledBench'


class BenchmarkEnabledTwo(benchmark.Benchmark):
  """ Second enabled benchmark for testing."""

  @classmethod
  def Name(cls):
    return 'EnabledBench2'


class BenchmarkDisabled(benchmark.Benchmark):
  """ Disabled benchmark for testing."""

  @classmethod
  def Name(cls):
    return 'DisabledBench'

  def GetExpectations(self):
    return DisabledExpectation()


class BenchmarkRunnerUnittest(unittest.TestCase):

  def setUp(self):
    self._stream = stream.TestOutputStream()
    self._mock_possible_browser = mock.MagicMock()
    self._mock_possible_browser.browser_type = 'TestBrowser'

  def testPrintBenchmarkListWithNoDisabledBenchmark(self):
    expected_printed_stream = (
        'Available benchmarks for TestBrowser are:\n'
        '  EnabledBench  Enabled benchmark for testing.\n'
        '  EnabledBench  Enabled benchmark for testing.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')
    benchmark_runner.PrintBenchmarkList([BenchmarkEnabled, BenchmarkEnabled],
                                        self._mock_possible_browser,
                                        self._stream)
    self.assertEquals(expected_printed_stream, self._stream.output_data)

  def testPrintBenchmarkListWithOneDisabledBenchmark(self):
    expected_printed_stream = (
        'Available benchmarks for TestBrowser are:\n'
        '  EnabledBench   Enabled benchmark for testing.\n'
        '\n'
        'Disabled benchmarks for TestBrowser are (force run with -d):\n'
        '  DisabledBench  Disabled benchmark for testing.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')

    benchmark_runner.PrintBenchmarkList([BenchmarkEnabled, BenchmarkDisabled],
                                        self._mock_possible_browser,
                                        self._stream)
    self.assertEquals(expected_printed_stream, self._stream.output_data)
