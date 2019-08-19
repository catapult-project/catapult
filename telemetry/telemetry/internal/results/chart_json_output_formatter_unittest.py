# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import StringIO
import unittest

from py_utils import tempfile_ext

from telemetry import story
from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import page_test_results
from telemetry.internal.results import results_processor
from telemetry import page as page_module
from telemetry.value import improvement_direction
from telemetry.value import list_of_scalar_values
from telemetry.value import scalar


def _MakeStorySet():
  ps = story.StorySet(base_dir=os.path.dirname(__file__))
  ps.AddStory(page_module.Page(
      'http://www.foo.com/', ps, ps.base_dir, name='http://www.foo.com/'))
  ps.AddStory(page_module.Page(
      'http://www.bar.com/', ps, ps.base_dir, name='http://www.bar.com/'))
  return ps


def _MakePageTestResults(
    description='benchmark_description', output_dir=None):
  return page_test_results.PageTestResults(
      benchmark_name='benchmark_name',
      benchmark_description=description,
      output_dir=output_dir)


class ChartJsonTest(unittest.TestCase):
  def setUp(self):
    self._output = StringIO.StringIO()
    self._story_set = _MakeStorySet()
    self._formatter = chart_json_output_formatter.ChartJsonOutputFormatter(
        self._output)

  def testOutputAndParse(self):
    with _MakePageTestResults() as results:
      self._output.truncate(0)

      results.WillRunPage(self._story_set[0])
      v0 = scalar.ScalarValue(results.current_story, 'foo', 'seconds', 3,
                              improvement_direction=improvement_direction.DOWN)
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

      self._formatter.Format(results)

    d = json.loads(self._output.getvalue())
    self.assertIn('foo', d['charts'])

  def testOutputAndParseNoResults(self):
    with _MakePageTestResults() as results:
      self._formatter.Format(results)

    d = json.loads(self._output.getvalue())
    self.assertEquals(d['benchmark_name'], 'benchmark_name')
    self.assertFalse(d['enabled'])

  def testAsChartDictSerializable(self):
    v0 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.WillRunPage(self._story_set[0])
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])

      d = chart_json_output_formatter.ResultsAsChartDict(results)
    json.dumps(d)

  def testAsChartDictBaseKeys(self):
    with _MakePageTestResults() as results:
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertEquals(d['format_version'], '0.1')
    self.assertEquals(d['next_version'], '0.2')
    self.assertEquals(d['benchmark_metadata']['name'], 'benchmark_name')
    self.assertEquals(d['benchmark_metadata']['description'],
                      'benchmark_description')
    self.assertEquals(d['benchmark_metadata']['type'], 'telemetry_benchmark')
    self.assertFalse(d['enabled'])

  def testAsChartDictNoDescription(self):
    with _MakePageTestResults(description=None) as results:
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertEquals('', d['benchmark_metadata']['description'])

  def testAsChartDictPageSpecificValuesSamePageWithGroupingLabel(self):
    page = self._story_set[0]
    page.grouping_keys['temperature'] = 'cold'
    v0 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    v1 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 4,
                            improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.WillRunPage(self._story_set[0])
      results.AddValue(v0)
      results.AddValue(v1)
      results.DidRunPage(self._story_set[0])
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('cold@@foo', d['charts'])
    self.assertIn('http://www.foo.com/', d['charts']['cold@@foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictPageSpecificValuesSamePageWithoutGroupingLabel(self):
    v0 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    v1 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 4,
                            improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.WillRunPage(self._story_set[0])
      results.AddValue(v0)
      results.AddValue(v1)
      results.DidRunPage(self._story_set[0])
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('foo', d['charts'])
    self.assertIn('http://www.foo.com/', d['charts']['foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictPageSpecificValuesAndComputedSummaryWithTraceName(self):
    v0 = scalar.ScalarValue(self._story_set[0], 'foo.bar', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    v1 = scalar.ScalarValue(self._story_set[1], 'foo.bar', 'seconds', 4,
                            improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.WillRunPage(self._story_set[0])
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])
      results.WillRunPage(self._story_set[1])
      results.AddValue(v1)
      results.DidRunPage(self._story_set[1])
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('foo', d['charts'])
    self.assertIn('http://www.foo.com/', d['charts']['foo'])
    self.assertIn('http://www.bar.com/', d['charts']['foo'])
    self.assertIn('bar', d['charts']['foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictPageSpecificValuesAndComputedSummaryWithoutTraceName(self):
    v0 = scalar.ScalarValue(self._story_set[0], 'foo', 'seconds', 3,
                            improvement_direction=improvement_direction.DOWN)
    v1 = scalar.ScalarValue(self._story_set[1], 'foo', 'seconds', 4,
                            improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.WillRunPage(self._story_set[0])
      results.AddValue(v0)
      results.DidRunPage(self._story_set[0])
      results.WillRunPage(self._story_set[1])
      results.AddValue(v1)
      results.DidRunPage(self._story_set[1])
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('foo', d['charts'])
    self.assertIn('http://www.foo.com/', d['charts']['foo'])
    self.assertIn('http://www.bar.com/', d['charts']['foo'])
    self.assertIn('summary', d['charts']['foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictSummaryValueWithTraceName(self):
    v0 = list_of_scalar_values.ListOfScalarValues(
        None, 'foo.bar', 'seconds', [3, 4],
        improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.AddSummaryValue(v0)
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('bar', d['charts']['foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictSummaryValueWithoutTraceName(self):
    v0 = list_of_scalar_values.ListOfScalarValues(
        None, 'foo', 'seconds', [3, 4],
        improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.AddSummaryValue(v0)
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertIn('summary', d['charts']['foo'])
    self.assertTrue(d['enabled'])

  def testAsChartDictWithTracesInArtifacts(self):
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      with _MakePageTestResults(output_dir=tempdir) as results:
        results.WillRunPage(self._story_set[0])
        with results.CreateArtifact(results_processor.HTML_TRACE_NAME):
          pass
        results.DidRunPage(self._story_set[0])

        d = chart_json_output_formatter.ResultsAsChartDict(results)

      self.assertIn('trace', d['charts'])
      self.assertIn('http://www.foo.com/', d['charts']['trace'])
      self.assertTrue(d['enabled'])

  def testAsChartDictValueSmokeTest(self):
    v0 = list_of_scalar_values.ListOfScalarValues(
        None, 'foo.bar', 'seconds', [3, 4],
        improvement_direction=improvement_direction.DOWN)
    with _MakePageTestResults() as results:
      results.AddSummaryValue(v0)
      d = chart_json_output_formatter.ResultsAsChartDict(results)

    self.assertEquals(d['charts']['foo']['bar']['values'], [3, 4])
