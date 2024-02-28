# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import json
import shutil
import sys
import tempfile
import unittest

import mock

from telemetry.core import exceptions
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_options
from telemetry.testing import test_stories
from tracing.trace_data import trace_data


def _CreateException():
  try:
    raise exceptions.IntentionalException
  except Exception: # pylint: disable=broad-except
    return sys.exc_info()


class PageTestResultsTest(unittest.TestCase):
  def setUp(self):
    self.stories = test_stories.DummyStorySet(['foo', 'bar', 'baz'])
    self.intermediate_dir = tempfile.mkdtemp()
    self._time_module = mock.patch(
        'telemetry.internal.results.page_test_results.time').start()
    self._time_module.time.return_value = 0

  def tearDown(self):
    shutil.rmtree(self.intermediate_dir)
    mock.patch.stopall()

  @property
  def mock_time(self):
    return self._time_module.time

  def CreateResults(self, **kwargs):
    kwargs.setdefault('intermediate_dir', self.intermediate_dir)
    return page_test_results.PageTestResults(**kwargs)

  def ReadTestResults(self):
    return results_options.ReadTestResults(self.intermediate_dir)

  def testFailures(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.Fail(_CreateException())
      with results.CreateStoryRun(self.stories[1]):
        pass

    self.assertTrue(results.had_failures)
    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 2)
    self.assertEqual(test_results[0]['status'], 'FAIL')
    self.assertEqual(test_results[1]['status'], 'PASS')

  def testSkips(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.Skip('testing reason')
      with results.CreateStoryRun(self.stories[1]):
        pass

    self.assertTrue(results.had_skips)
    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 2)
    self.assertEqual(test_results[0]['status'], 'SKIP')
    self.assertEqual(test_results[1]['status'], 'PASS')

  def testBenchmarkInterruption(self):
    reason = 'This is a reason'
    with self.CreateResults() as results:
      self.assertIsNone(results.benchmark_interruption)
      self.assertFalse(results.benchmark_interrupted)
      results.InterruptBenchmark(reason)

    self.assertEqual(results.benchmark_interruption, reason)
    self.assertTrue(results.benchmark_interrupted)

  def testUncaughtExceptionInterruptsBenchmark(self):
    with self.assertRaises(ValueError):
      with self.CreateResults() as results:
        with results.CreateStoryRun(self.stories[0]):
          raise ValueError('expected error')

    self.assertTrue(results.benchmark_interrupted)
    # In Python2, the exc_value has a extra comma like:
    #     ValueError('expected error',)
    # while in Python3, exc_value is like:
    #     ValueError('expected error')
    self.assertIn("ValueError('expected error'",
                  results.benchmark_interruption)

  def testPassesNoSkips(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.Fail(_CreateException())
      with results.CreateStoryRun(self.stories[1]):
        pass
      with results.CreateStoryRun(self.stories[2]):
        results.Skip('testing reason')

    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 3)
    self.assertEqual(test_results[0]['status'], 'FAIL')
    self.assertEqual(test_results[1]['status'], 'PASS')
    self.assertEqual(test_results[2]['status'], 'SKIP')


  def testAddMeasurementAsScalar(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.AddMeasurement('a', 'seconds', 3)

    test_results = self.ReadTestResults()
    self.assertTrue(len(test_results), 1)
    measurements = results_options.ReadMeasurements(test_results[0])
    self.assertEqual(measurements, {'a': {'unit': 'seconds', 'samples': [3]}})

  def testAddMeasurementAsList(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.AddMeasurement('a', 'seconds', [1, 2, 3])

    test_results = self.ReadTestResults()
    self.assertTrue(len(test_results), 1)
    measurements = results_options.ReadMeasurements(test_results[0])
    self.assertEqual(measurements,
                     {'a': {'unit': 'seconds', 'samples': [1, 2, 3]}})

  def testNonNumericMeasurementIsInvalid(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        with self.assertRaises(TypeError):
          results.AddMeasurement('url', 'string', 'foo')

  def testMeasurementUnitChangeRaises(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.AddMeasurement('a', 'seconds', 3)
      with results.CreateStoryRun(self.stories[1]):
        with self.assertRaises(ValueError):
          results.AddMeasurement('a', 'foobgrobbers', 3)

  def testNoSuccessesWhenAllStoriesFailOrSkip(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.Fail('message')
      with results.CreateStoryRun(self.stories[1]):
        results.Skip('message')
    self.assertFalse(results.had_successes)

  def testAddTraces(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.AddTraces(trace_data.CreateTestTrace(1))
      with results.CreateStoryRun(self.stories[1]):
        results.AddTraces(trace_data.CreateTestTrace(2))

    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 2)
    for test_result in test_results:
      trace_names = [name for name in test_result['outputArtifacts']
                     if name.startswith('trace/')]
      self.assertTrue(len(trace_names), 1)

  def testAddTracesForSameStory(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        results.AddTraces(trace_data.CreateTestTrace(1))
        results.AddTraces(trace_data.CreateTestTrace(2))

    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 1)
    for test_result in test_results:
      trace_names = [name for name in test_result['outputArtifacts']
                     if name.startswith('trace/')]
      self.assertTrue(len(trace_names), 2)

  def testDiagnosticsAsArtifact(self):
    with self.CreateResults(benchmark_name='some benchmark',
                            benchmark_description='a description',
                            bot_id_name='some bot ID') as results:
      results.AddSharedDiagnostics(
          owners=['test'],
          bug_components=['1', '2'],
          documentation_urls=[['documentation', 'url']],
          architecture='arch',
          device_id='id',
          os_name='os',
          os_version='ver',
          os_detail_vers='detailed_ver'
      )
      with results.CreateStoryRun(self.stories[0]):
        pass
      with results.CreateStoryRun(self.stories[1]):
        pass

    test_results = self.ReadTestResults()
    self.assertEqual(len(test_results), 2)
    for test_result in test_results:
      self.assertEqual(test_result['status'], 'PASS')
      artifacts = test_result['outputArtifacts']
      self.assertIn(page_test_results.DIAGNOSTICS_NAME, artifacts)
      with open(artifacts[page_test_results.DIAGNOSTICS_NAME]['filePath']) as f:
        diagnostics = json.load(f)
      self.assertEqual(diagnostics, {
          'diagnostics': {
              'benchmarks': ['some benchmark'],
              'benchmarkDescriptions': ['a description'],
              'botId': ['some bot ID'],
              'owners': ['test'],
              'bugComponents': ['1', '2'],
              'documentationLinks': [['documentation', 'url']],
              'architectures': ['arch'],
              'deviceIds': ['id'],
              'osNames': ['os'],
              'osVersions': ['ver'],
              'osDetailedVersions': ['detailed_ver'],
          },
      })

  def testCreateArtifactsForDifferentStories(self):
    with self.CreateResults() as results:
      with results.CreateStoryRun(self.stories[0]):
        with results.CreateArtifact('log.txt') as log_file:
          log_file.write('story0\n')
      with results.CreateStoryRun(self.stories[1]):
        with results.CreateArtifact('log.txt') as log_file:
          log_file.write('story1\n')

    test_results = self.ReadTestResults()
    with open(test_results[0]['outputArtifacts']['log.txt']['filePath']) as f:
      self.assertEqual(f.read(), 'story0\n')
    with open(test_results[1]['outputArtifacts']['log.txt']['filePath']) as f:
      self.assertEqual(f.read(), 'story1\n')
