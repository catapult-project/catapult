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

  def testShouldDisable(self):
    """Ensure that overridden ShouldDisable class methods are respected."""
    expected_printed_stream = (
        'Available benchmarks for TestBrowser are:\n'
        '  EnabledBench   Enabled benchmark for testing.\n'
        '\n'
        'Disabled benchmarks for TestBrowser are (force run with -d):\n'
        '  DisabledBench  Disabled benchmark for testing.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')

    @classmethod
    def FakeShouldDisable(cls, possible_browser):
      del possible_browser  # unused
      return cls is BenchmarkDisabled

    BenchmarkDisabled.ShouldDisable = FakeShouldDisable
    BenchmarkEnabled.ShouldDisable = FakeShouldDisable
    benchmark_runner.PrintBenchmarkList(
        [BenchmarkDisabled, BenchmarkEnabled], self._mock_possible_browser,
        self._stream)
    self.assertEquals(expected_printed_stream, self._stream.output_data)

  def testShouldDisableComplex(self):
    """Ensure that browser-dependent ShouldDisable overrides are respected."""
    expected_printed_stream = (
        # Expected output for 'TestBrowser':
        'Available benchmarks for TestBrowser are:\n'
        '  EnabledBench   Enabled benchmark for testing.\n'
        '\n'
        'Disabled benchmarks for TestBrowser are (force run with -d):\n'
        '  EnabledBench2  Second enabled benchmark for testing.\n'
        'Pass --browser to list benchmarks for another browser.\n\n'
        # Expected output for 'MockBrowser':
        'Available benchmarks for MockBrowser are:\n'
        '  EnabledBench   Enabled benchmark for testing.\n'
        '  EnabledBench2  Second enabled benchmark for testing.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')

    @classmethod
    def FakeShouldDisable(cls, possible_browser):
      return (
          cls is BenchmarkEnabledTwo and
          not 'Mock' in possible_browser.browser_type)

    BenchmarkEnabled.ShouldDisable = FakeShouldDisable
    BenchmarkEnabledTwo.ShouldDisable = FakeShouldDisable
    benchmark_runner.PrintBenchmarkList(
        [BenchmarkEnabled, BenchmarkEnabledTwo], self._mock_possible_browser,
        self._stream)
    self._mock_possible_browser.browser_type = 'MockBrowser'
    benchmark_runner.PrintBenchmarkList(
        [BenchmarkEnabled, BenchmarkEnabledTwo], self._mock_possible_browser,
        self._stream)
    self.assertEquals(expected_printed_stream, self._stream.output_data)
