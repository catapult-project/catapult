# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry import benchmark
from telemetry import benchmark_runner
from telemetry.core import util
from telemetry.unittest_util import stream

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock # pylint: disable=F0401


class BenchmarkFoo(benchmark.Benchmark):
  """ Benchmark Foo for testing."""

  @classmethod
  def Name(cls):
    return 'FooBenchmark'


class BenchmarkBar(benchmark.Benchmark):
  """ Benchmark Bar for testing long description line."""

  @classmethod
  def Name(cls):
    return 'BarBenchmarkkkkk'

class UnusualBenchmark(benchmark.Benchmark):
  @classmethod
  def Name(cls):
    return 'I have a very unusual name'


class BenchmarkRunnerUnittest(unittest.TestCase):
  def setUp(self):
    self._stream = stream.TestOutputStream()
    self._mock_possible_browser = mock.MagicMock()
    self._mock_possible_browser.browser_type = 'TestBrowser'

  def testPrintBenchmarkListWithNoDisabledBenchmark(self):
    expected_printed_stream = (
        'Available benchmarks for TestBrowser are:\n'
        '  FooBenchmark      Benchmark Foo for testing.\n'
        '  BarBenchmarkkkkk  Benchmark Bar for testing long description line.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')
    with mock.patch('telemetry.benchmark_runner.decorators') as mock_module:
      mock_module.IsEnabled.return_value = (True, None)
      benchmark_runner.PrintBenchmarkList(
        [BenchmarkFoo, BenchmarkBar], self._mock_possible_browser, self._stream)
      self.assertEquals(expected_printed_stream, self._stream.output_data)

  def testPrintBenchmarkListWithOneDisabledBenchmark(self):
    self._mock_possible_browser.browser_type = 'TestBrowser'
    expected_printed_stream = (
        'Available benchmarks for TestBrowser are:\n'
        '  FooBenchmark      Benchmark Foo for testing.\n'
        '\n'
        'Disabled benchmarks for TestBrowser are (force run with -d):\n'
        '  BarBenchmarkkkkk  Benchmark Bar for testing long description line.\n'
        'Pass --browser to list benchmarks for another browser.\n\n')
    with mock.patch('telemetry.benchmark_runner.decorators') as mock_module:
      def FakeIsEnabled(benchmark_class, _):
        if benchmark_class is BenchmarkFoo:
          return True, None
        else:
          return False, 'Only supported BenchmarkFoo'
      mock_module.IsEnabled = FakeIsEnabled
      benchmark_runner.PrintBenchmarkList(
        [BenchmarkFoo, BenchmarkBar], self._mock_possible_browser, self._stream)
      self.assertEquals(expected_printed_stream, self._stream.output_data)

  def testGetMostLikelyMatchedBenchmarks(self):
    all_benchmarks = [BenchmarkFoo, BenchmarkBar, UnusualBenchmark]
    self.assertEquals(
        [BenchmarkFoo, BenchmarkBar],
        benchmark_runner.GetMostLikelyMatchedBenchmarks(
            all_benchmarks, 'BenchmarkFooz'))

    self.assertEquals(
        [BenchmarkBar, BenchmarkFoo],
        benchmark_runner.GetMostLikelyMatchedBenchmarks(
            all_benchmarks, 'BarBenchmark'))

    self.assertEquals(
        [UnusualBenchmark],
        benchmark_runner.GetMostLikelyMatchedBenchmarks(
            all_benchmarks, 'unusual'))
