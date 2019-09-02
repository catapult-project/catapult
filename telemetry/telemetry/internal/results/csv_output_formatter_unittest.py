# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import os
import shutil
import StringIO
import tempfile
import unittest

import mock

from telemetry import story
from telemetry.internal.results import csv_output_formatter
from telemetry.internal.results import page_test_results
from telemetry import page as page_module
from tracing.trace_data import trace_data


def _MakeStorySet():
  story_set = story.StorySet(base_dir=os.path.dirname(__file__))
  story_set.AddStory(page_module.Page(
      'http://www.foo.com/', story_set, story_set.base_dir,
      name='http://www.foo.com/'))
  story_set.AddStory(page_module.Page(
      'http://www.bar.com/', story_set, story_set.base_dir,
      name='http://www.bar.com/'))
  return story_set


class CsvOutputFormatterTest(unittest.TestCase):

  def setUp(self):
    self._output = StringIO.StringIO()
    self._story_set = _MakeStorySet()
    self._temp_dir = tempfile.mkdtemp()
    with mock.patch('time.time', return_value=15e8):
      self._results = page_test_results.PageTestResults(
          benchmark_name='benchmark',
          benchmark_description='foo',
          output_dir=self._temp_dir,
          upload_bucket='fake_bucket')
    self._formatter = csv_output_formatter.CsvOutputFormatter(self._output)

  def tearDown(self):
    self._results.Finalize()
    shutil.rmtree(self._temp_dir)

  def Format(self):
    self._results.PopulateHistogramSet()
    self._formatter.Format(self._results)
    return self._output.getvalue()

  def testSimple(self):
    # Test a simple benchmark with only one value:
    self._results.WillRunPage(self._story_set[0])
    self._results.AddMeasurement('foo', 'seconds', 3)
    self._results.DidRunPage(self._story_set[0])

    actual = list(zip(*csv.reader(self.Format().splitlines())))
    expected = [
        ('name', 'foo'), ('unit', 'ms'), ('avg', '3000'), ('count', '1'),
        ('max', '3000'), ('min', '3000'), ('std', '0'), ('sum', '3000'),
        ('architectures', ''), ('benchmarks', 'benchmark'),
        ('benchmarkStart', '2017-07-14 02:40:00'), ('bots', ''), ('builds', ''),
        ('deviceIds', ''), ('displayLabel', 'benchmark 2017-07-14 02:40:00'),
        ('masters', ''), ('memoryAmounts', ''), ('osNames', ''),
        ('osVersions', ''), ('productVersions', ''),
        ('stories', 'http://www.foo.com/'), ('storysetRepeats', ''),
        ('traceStart', ''), ('traceUrls', '')
    ]
    self.assertEqual(actual, expected)

  @mock.patch('py_utils.cloud_storage.Insert')
  def testMultiplePagesAndValues(self, cloud_storage_insert_patch):
    cloud_storage_insert_patch.return_value = 'fake_url'

    self._results.WillRunPage(self._story_set[0])
    self._results.AddMeasurement('foo', 'seconds', 4)
    self._results.DidRunPage(self._story_set[0])

    self._results.WillRunPage(self._story_set[1])
    self._results.AddMeasurement('foo', 'seconds', 3.4)
    self._results.AddTraces(trace_data.CreateTestTrace())
    self._results.AddMeasurement('bar', 'km', 10)
    self._results.AddMeasurement('baz', 'count', 5)
    self._results.DidRunPage(self._story_set[1])

    # Parse CSV output into list of lists.
    values = list(csv.reader(self.Format().splitlines()))[1:]
    values.sort()

    self.assertEquals(len(values), 4)
    self.assertEquals(len(set((v[1] for v in values))), 2)  # 2 pages.
    self.assertEquals(len(set((v[2] for v in values))), 4)  # 4 value names.
    sample_row = values[2]
    self.assertEquals(sample_row, [
        'foo', 'ms', '3400', '1', '3400', '3400', '0', '3400', '', 'benchmark',
        '2017-07-14 02:40:00', '', '', '', 'benchmark 2017-07-14 02:40:00', '',
        '', '', '', '', 'http://www.bar.com/', '', '', 'fake_url'])
