# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import os
import unittest

from py_utils import tempfile_ext
import mock

from telemetry import benchmark
from telemetry import story
from telemetry.internal.results import artifact_results as ar_module
from telemetry.internal.results import base_test_results_unittest
from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import html_output_formatter
from telemetry.internal.results import page_test_results
from telemetry import page as page_module
from telemetry.value import histogram
from telemetry.value import improvement_direction
from telemetry.value import scalar
from telemetry.value import skip
from telemetry.value import trace
from tracing.trace_data import trace_data
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import date_range
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


class TelemetryInfoTest(unittest.TestCase):
  def testBenchmarkDescriptionNotPopulatedIfNotSet(self):
    ti = page_test_results.TelemetryInfo()
    ti.benchmark_name = 'benchmark'
    ti.benchmark_start_epoch = 123
    ti_dict = ti.AsDict()
    self.assertNotIn(reserved_infos.BENCHMARK_DESCRIPTIONS.name, ti_dict)

  def testBenchmarkDescriptionPopulatedIfSet(self):
    ti = page_test_results.TelemetryInfo()
    ti.benchmark_name = 'benchmark'
    ti.benchmark_start_epoch = 123
    ti.benchmark_descriptions = 'foo'
    ti_dict = ti.AsDict()
    self.assertIn(reserved_infos.BENCHMARK_DESCRIPTIONS.name, ti_dict)
    self.assertEqual(ti_dict[reserved_infos.BENCHMARK_DESCRIPTIONS.name],
                     ['foo'])

  def testTraceLocalPathWithoutLabel(self):
    ti = page_test_results.TelemetryInfo(output_dir='/tmp')
    ti.benchmark_name = 'benchmark'
    ti.benchmark_start_epoch = 123
    ti.benchmark_descriptions = 'foo'
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    bar_story = page_module.Page("http://www.bar.com/", story_set,
                                 story_set.base_dir,
                                 name='http://www.bar.com/')
    story_set.AddStory(bar_story)
    ti.WillRunStory(bar_story, None)
    self.assertIn('www_bar_com', ti.trace_local_path)
    self.assertNotIn('custom_label', ti.trace_local_path)

  def testTraceLocalPathWithLabel(self):
    ti = page_test_results.TelemetryInfo(output_dir='/tmp')
    ti.benchmark_name = 'benchmark'
    ti.benchmark_start_epoch = 123
    ti.benchmark_descriptions = 'foo'
    ti.label = 'custom_label'
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    bar_story = page_module.Page("http://www.bar.com/", story_set,
                                 story_set.base_dir,
                                 name='http://www.bar.com/')
    story_set.AddStory(bar_story)
    ti.WillRunStory(bar_story, None)
    self.assertIn('www_bar_com', ti.trace_local_path)
    self.assertIn('custom_label', ti.trace_local_path)

  def testGetDiagnostics(self):
    ti = page_test_results.TelemetryInfo()
    ti.benchmark_name = 'benchmark'
    ti.benchmark_start_epoch = 123
    ti.benchmark_descriptions = 'foo'
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    foo_story = page_module.Page("http://www.foo.com/", story_set,
                                 story_set.base_dir,
                                 name='story1')
    story_set.AddStory(foo_story)
    ti.WillRunStory(foo_story, None)
    ti_diags = ti.diagnostics


    self.assertEqual(len(ti_diags), 5)
    self.assertIn(reserved_infos.BENCHMARKS.name, ti_diags)
    name_diag = ti_diags[reserved_infos.BENCHMARKS.name]
    self.assertIsInstance(name_diag, generic_set.GenericSet)
    self.assertIn(reserved_infos.BENCHMARK_START.name, ti_diags)
    start_diag = ti_diags[reserved_infos.BENCHMARK_START.name]
    self.assertIsInstance(start_diag, date_range.DateRange)
    self.assertIn(reserved_infos.BENCHMARK_DESCRIPTIONS.name, ti_diags)
    desc_diag = ti_diags[reserved_infos.BENCHMARK_DESCRIPTIONS.name]
    self.assertIsInstance(desc_diag, generic_set.GenericSet)
    self.assertIn(reserved_infos.STORIES.name, ti_diags)
    story_diag = ti_diags[reserved_infos.STORIES.name]
    self.assertIsInstance(story_diag, generic_set.GenericSet)
    self.assertEquals(story_diag.AsDict()['values'], ['story1'])


    # Now reset the story and assert that we update the diagnostics.
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    bar_story = page_module.Page("http://www.bar.com/", story_set,
                                 story_set.base_dir,
                                 name='story2')
    story_set.AddStory(bar_story)
    ti.WillRunStory(bar_story, None)

    # Assert everything is the same except for the story
    ti_diags = ti.diagnostics
    self.assertEqual(len(ti_diags), 5)
    self.assertIn(reserved_infos.BENCHMARKS.name, ti_diags)
    self.assertEqual(name_diag, ti_diags[reserved_infos.BENCHMARKS.name])
    self.assertIn(reserved_infos.BENCHMARK_START.name, ti_diags)
    self.assertEqual(start_diag, ti_diags[reserved_infos.BENCHMARK_START.name])
    self.assertIn(reserved_infos.BENCHMARK_DESCRIPTIONS.name, ti_diags)
    self.assertEqual(
        desc_diag, ti_diags[reserved_infos.BENCHMARK_DESCRIPTIONS.name])
    self.assertIn(reserved_infos.STORIES.name, ti_diags)
    story_diag = ti_diags[reserved_infos.STORIES.name]
    self.assertIsInstance(story_diag, generic_set.GenericSet)
    self.assertEquals(story_diag.AsDict()['values'], ['story2'])



class PageTestResultsTest(base_test_results_unittest.BaseTestResultsUnittest):
  def setUp(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(page_module.Page("http://www.bar.com/", story_set,
                                        story_set.base_dir,
                                        name='http://www.bar.com/'))
    story_set.AddStory(page_module.Page("http://www.baz.com/", story_set,
                                        story_set.base_dir,
                                        name='http://www.baz.com/'))
    story_set.AddStory(page_module.Page("http://www.foo.com/", story_set,
                                        story_set.base_dir,
                                        name='http://www.foo.com/'))
    self.story_set = story_set

  @property
  def pages(self):
    return self.story_set.stories

  def getPageTestResults(self, output_formatters=None, benchmark_metadata=None,
                         start=123, benchmark_enabled=True):
    results = page_test_results.PageTestResults(
        benchmark_metadata=benchmark_metadata,
        output_formatters=output_formatters,
        benchmark_enabled=benchmark_enabled)
    results.telemetry_info.benchmark_name = 'benchmark'
    results.telemetry_info.benchmark_start_epoch = start
    results.telemetry_info.benchmark_descriptions = 'foo'
    return results

  def testFailures(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.Fail(self.CreateException())
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.DidRunPage(self.pages[1])

    self.assertEqual(set([self.pages[0]]), results.pages_that_failed)
    self.assertEqual(set([self.pages[1]]), results.pages_that_succeeded)

    self.assertEqual(len(results.all_page_runs), 2)
    self.assertTrue(results.had_failures)
    self.assertTrue(results.all_page_runs[0].failed)
    self.assertTrue(results.all_page_runs[1].ok)

  def testSkips(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.Skip('testing reason')
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.DidRunPage(self.pages[1])

    self.assertTrue(results.all_page_runs[0].skipped)
    self.assertEqual(self.pages[0], results.all_page_runs[0].story)
    self.assertEqual(set([self.pages[0], self.pages[1]]),
                     results.pages_that_succeeded)

    self.assertEqual(2, len(results.all_page_runs))
    self.assertTrue(results.all_page_runs[0].skipped)
    self.assertTrue(results.all_page_runs[1].ok)

  def testInterruptMiddleRun(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[1])
    results.DidRunPage(self.pages[1])
    results.InterruptBenchmark(self.pages, 2)

    self.assertEqual(6, len(results.all_page_runs))
    self.assertTrue(results.all_page_runs[0].ok)
    self.assertTrue(results.all_page_runs[1].skipped)
    self.assertTrue(results.all_page_runs[2].skipped)
    self.assertTrue(results.all_page_runs[3].skipped)
    self.assertTrue(results.all_page_runs[4].skipped)
    self.assertTrue(results.all_page_runs[5].skipped)

  def testInterruptBeginningRun(self):
    results = self.getPageTestResults()
    results.InterruptBenchmark(self.pages, 1)

    self.assertTrue(results.all_page_runs[0].skipped)
    self.assertEqual(self.pages[0], results.all_page_runs[0].story)
    self.assertEqual(set([]),
                     results.pages_that_succeeded_and_not_skipped)

    self.assertEqual(3, len(results.all_page_runs))
    self.assertTrue(results.all_page_runs[0].skipped)
    self.assertTrue(results.all_page_runs[1].skipped)
    self.assertTrue(results.all_page_runs[2].skipped)

  def testPassesNoSkips(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.Fail(self.CreateException())
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.DidRunPage(self.pages[1])

    results.WillRunPage(self.pages[2])
    results.Skip('testing reason')
    results.DidRunPage(self.pages[2])

    self.assertEqual(set([self.pages[0]]), results.pages_that_failed)
    self.assertEqual(set([self.pages[1], self.pages[2]]),
                     results.pages_that_succeeded)
    self.assertEqual(set([self.pages[1]]),
                     results.pages_that_succeeded_and_not_skipped)

    self.assertEqual(3, len(results.all_page_runs))
    self.assertTrue(results.all_page_runs[0].failed)
    self.assertTrue(results.all_page_runs[1].ok)
    self.assertTrue(results.all_page_runs[2].skipped)

  def testBasic(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[1])

    results.PrintSummary()

    values = results.FindPageSpecificValuesForPage(self.pages[0], 'a')
    self.assertEquals(1, len(values))
    v = values[0]
    self.assertEquals(v.name, 'a')
    self.assertEquals(v.page, self.pages[0])

    values = results.FindAllPageSpecificValuesNamed('a')
    assert len(values) == 2

  def testAddValueWithStoryGroupingKeys(self):
    results = self.getPageTestResults()
    self.pages[0].grouping_keys['foo'] = 'bar'
    self.pages[0].grouping_keys['answer'] = '42'
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])

    results.PrintSummary()

    values = results.FindPageSpecificValuesForPage(self.pages[0], 'a')
    v = values[0]
    self.assertEquals(v.grouping_keys['foo'], 'bar')
    self.assertEquals(v.grouping_keys['answer'], '42')
    self.assertEquals(v.tir_label, '42_bar')

  def testAddValueWithStoryGroupingKeysAndMatchingTirLabel(self):
    results = self.getPageTestResults()
    self.pages[0].grouping_keys['foo'] = 'bar'
    self.pages[0].grouping_keys['answer'] = '42'
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP,
        tir_label='42_bar'))
    results.DidRunPage(self.pages[0])

    results.PrintSummary()

    values = results.FindPageSpecificValuesForPage(self.pages[0], 'a')
    v = values[0]
    self.assertEquals(v.grouping_keys['foo'], 'bar')
    self.assertEquals(v.grouping_keys['answer'], '42')
    self.assertEquals(v.tir_label, '42_bar')

  def testAddValueWithStoryGroupingKeysAndMismatchingTirLabel(self):
    results = self.getPageTestResults()
    self.pages[0].grouping_keys['foo'] = 'bar'
    self.pages[0].grouping_keys['answer'] = '42'
    results.WillRunPage(self.pages[0])
    with self.assertRaises(AssertionError):
      results.AddValue(scalar.ScalarValue(
          self.pages[0], 'a', 'seconds', 3,
          improvement_direction=improvement_direction.UP,
          tir_label='another_label'))

  def testAddValueWithDuplicateStoryGroupingKeyFails(self):
    results = self.getPageTestResults()
    self.pages[0].grouping_keys['foo'] = 'bar'
    results.WillRunPage(self.pages[0])
    with self.assertRaises(AssertionError):
      results.AddValue(scalar.ScalarValue(
          self.pages[0], 'a', 'seconds', 3,
          improvement_direction=improvement_direction.UP,
          grouping_keys={'foo': 'bar'}))

  def testUrlIsInvalidValue(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    self.assertRaises(
        AssertionError,
        lambda: results.AddValue(scalar.ScalarValue(
            self.pages[0], 'url', 'string', 'foo',
            improvement_direction=improvement_direction.UP)))

  def testAddSummaryValueWithPageSpecified(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    self.assertRaises(
        AssertionError,
        lambda: results.AddSummaryValue(scalar.ScalarValue(
            self.pages[0], 'a', 'units', 3,
            improvement_direction=improvement_direction.UP)))

  def testUnitChange(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    self.assertRaises(
        AssertionError,
        lambda: results.AddValue(scalar.ScalarValue(
            self.pages[1], 'a', 'foobgrobbers', 3,
            improvement_direction=improvement_direction.UP)))

  def testTypeChange(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    self.assertRaises(
        AssertionError,
        lambda: results.AddValue(histogram.HistogramValue(
            self.pages[1], 'a', 'seconds',
            raw_value_json='{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
            improvement_direction=improvement_direction.UP)))

  def testGetPagesThatSucceededAllPagesFail(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.Fail('message')
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 7,
        improvement_direction=improvement_direction.UP))
    results.Fail('message')
    results.DidRunPage(self.pages[1])

    results.PrintSummary()
    self.assertEquals(0, len(results.pages_that_succeeded))

  def testGetSuccessfulPageValuesMergedNoFailures(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    self.assertEquals(1, len(results.all_page_specific_values))
    results.DidRunPage(self.pages[0])

  def testGetAllValuesForSuccessfulPages(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    value1 = scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP)
    results.AddValue(value1)
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    value2 = scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP)
    results.AddValue(value2)
    results.DidRunPage(self.pages[1])

    results.WillRunPage(self.pages[2])
    value3 = scalar.ScalarValue(
        self.pages[2], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP)
    results.AddValue(value3)
    results.DidRunPage(self.pages[2])

    self.assertEquals(
        [value1, value2, value3], results.all_page_specific_values)

  def testFindValues(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    v0 = scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP)
    results.AddValue(v0)
    v1 = scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 4,
        improvement_direction=improvement_direction.UP)
    results.AddValue(v1)
    results.DidRunPage(self.pages[1])

    values = results.FindValues(lambda v: v.value == 3)
    self.assertEquals([v0], values)

  def testValueWithTIRLabel(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    v0 = scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3, tir_label='foo',
        improvement_direction=improvement_direction.UP)
    results.AddValue(v0)
    v1 = scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3, tir_label='bar',
        improvement_direction=improvement_direction.UP)
    results.AddValue(v1)
    results.DidRunPage(self.pages[0])

    values = results.FindAllPageSpecificValuesFromIRNamed('foo', 'a')
    self.assertEquals([v0], values)

  def testTraceValue(self):
    results = self.getPageTestResults()
    results.WillRunPage(self.pages[0])
    results.AddValue(trace.TraceValue(
        None, trace_data.CreateTraceDataFromRawData([[{'test': 1}]])))
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(trace.TraceValue(
        None, trace_data.CreateTraceDataFromRawData([[{'test': 2}]])))
    results.DidRunPage(self.pages[1])

    results.PrintSummary()

    values = results.FindAllTraceValues()
    self.assertEquals(2, len(values))

  def testCleanUpCleansUpTraceValues(self):
    results = self.getPageTestResults()
    v0 = trace.TraceValue(
        None, trace_data.CreateTraceDataFromRawData([{'test': 1}]))
    v1 = trace.TraceValue(
        None, trace_data.CreateTraceDataFromRawData([{'test': 2}]))

    results.WillRunPage(self.pages[0])
    results.AddValue(v0)
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(v1)
    results.DidRunPage(self.pages[1])

    results.CleanUp()
    self.assertTrue(v0.cleaned_up)
    self.assertTrue(v1.cleaned_up)

  def testNoTracesLeftAfterCleanUp(self):
    results = self.getPageTestResults()
    v0 = trace.TraceValue(None,
                          trace_data.CreateTraceDataFromRawData([{'test': 1}]))
    v1 = trace.TraceValue(None,
                          trace_data.CreateTraceDataFromRawData([{'test': 2}]))

    results.WillRunPage(self.pages[0])
    results.AddValue(v0)
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(v1)
    results.DidRunPage(self.pages[1])

    results.CleanUp()
    self.assertFalse(results.FindAllTraceValues())

  def testPrintSummaryDisabledResults(self):
    output_stream = StringIO.StringIO()
    output_formatters = []
    benchmark_metadata = benchmark.BenchmarkMetadata(
        'benchmark_name', 'benchmark_description')
    output_formatters.append(
        chart_json_output_formatter.ChartJsonOutputFormatter(
            output_stream, benchmark_metadata))
    output_formatters.append(html_output_formatter.HtmlOutputFormatter(
        output_stream, benchmark_metadata, True))
    results = self.getPageTestResults(
        output_formatters=output_formatters, benchmark_enabled=False)
    results.PrintSummary()
    self.assertEquals(
        output_stream.getvalue(),
        '{\n  \"enabled\": false,\n  ' +
        '\"benchmark_name\": \"benchmark_name\"\n}\n')

  def testImportHistogramDicts(self):
    hs = histogram_set.HistogramSet()
    hs.AddHistogram(histogram_module.Histogram('foo', 'count'))
    hs.AddSharedDiagnosticToAllHistograms(
        'bar', generic_set.GenericSet(['baz']))
    histogram_dicts = hs.AsDicts()
    results = self.getPageTestResults(start=1501773200)
    results.WillRunPage(self.pages[0])
    results.ImportHistogramDicts(histogram_dicts)
    results.DidRunPage(self.pages[0])
    self.assertEqual(results.AsHistogramDicts(), histogram_dicts)

  def testImportHistogramDicts_DelayedImport(self):
    hs = histogram_set.HistogramSet()
    hs.AddHistogram(histogram_module.Histogram('foo', 'count'))
    hs.AddSharedDiagnosticToAllHistograms(
        'bar', generic_set.GenericSet(['baz']))
    histogram_dicts = hs.AsDicts()
    benchmark_metadata = benchmark.BenchmarkMetadata(
        'benchmark_name', 'benchmark_description')
    results = self.getPageTestResults(
        benchmark_metadata=benchmark_metadata, start=1501773200)
    results.WillRunPage(self.pages[0])
    results.ImportHistogramDicts(histogram_dicts, import_immediately=False)
    results.DidRunPage(self.pages[0])
    self.assertEqual(len(results.AsHistogramDicts()), 0)
    results.PopulateHistogramSet()
    self.assertEqual(results.AsHistogramDicts(), histogram_dicts)

  def testAddSharedDiagnosticToAllHistograms(self):
    benchmark_metadata = benchmark.BenchmarkMetadata(
        'benchmark_name', 'benchmark_description')
    results = self.getPageTestResults(
        benchmark_metadata=benchmark_metadata, start=1501773200)
    results.WillRunPage(self.pages[0])
    results.DidRunPage(self.pages[0])
    results.CleanUp()
    results.AddSharedDiagnosticToAllHistograms(
        reserved_infos.BENCHMARKS.name,
        generic_set.GenericSet(['benchmark_name']))

    results.PopulateHistogramSet()

    histogram_dicts = results.AsHistogramDicts()
    self.assertEquals(1, len(histogram_dicts))

    diag = diagnostic.Diagnostic.FromDict(histogram_dicts[0])
    self.assertIsInstance(diag, generic_set.GenericSet)

  def testPopulateHistogramSet_UsesScalarValueData(self):
    benchmark_metadata = benchmark.BenchmarkMetadata(
        'benchmark_name', 'benchmark_description')
    results = self.getPageTestResults(
        benchmark_metadata=benchmark_metadata, start=1501773200)
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])
    results.CleanUp()

    results.PopulateHistogramSet()

    hs = histogram_set.HistogramSet()
    hs.ImportDicts(results.AsHistogramDicts())
    self.assertEquals(1, len(hs))
    self.assertEquals('a', hs.GetFirstHistogram().name)

  def testPopulateHistogramSet_UsesHistogramSetData(self):
    original_diagnostic = generic_set.GenericSet(['benchmark_name'])

    benchmark_metadata = benchmark.BenchmarkMetadata(
        'benchmark_name', 'benchmark_description')
    results = self.getPageTestResults(
        benchmark_metadata=benchmark_metadata)
    results.WillRunPage(self.pages[0])
    results.AddHistogram(histogram_module.Histogram('foo', 'count'))
    results.AddSharedDiagnosticToAllHistograms(
        reserved_infos.BENCHMARKS.name, original_diagnostic)
    results.DidRunPage(self.pages[0])
    results.CleanUp()

    results.PopulateHistogramSet()

    histogram_dicts = results.AsHistogramDicts()
    self.assertEquals(7, len(histogram_dicts))

    hs = histogram_set.HistogramSet()
    hs.ImportDicts(histogram_dicts)

    diag = hs.LookupDiagnostic(original_diagnostic.guid)
    self.assertIsInstance(diag, generic_set.GenericSet)


class PageTestResultsFilterTest(unittest.TestCase):
  def setUp(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(
        page_module.Page('http://www.foo.com/', story_set, story_set.base_dir,
                         name='http://www.foo.com'))
    story_set.AddStory(
        page_module.Page('http://www.bar.com/', story_set, story_set.base_dir,
                         name='http://www.bar.com/'))
    self.story_set = story_set

  def getPageTestResults(self, should_add_value=None, upload_bucket=None,
                         artifact_results=None):
    results = page_test_results.PageTestResults(
        should_add_value=should_add_value,
        upload_bucket=upload_bucket, artifact_results=artifact_results)
    results.telemetry_info.benchmark_name = 'benchmark'
    results.telemetry_info.benchmark_start_epoch = 123
    results.telemetry_info.benchmark_descriptions = 'foo'
    return results

  @property
  def pages(self):
    return self.story_set.stories

  def testFilterValue(self):
    def AcceptValueNamed_a(name, _):
      return name == 'a'
    results = self.getPageTestResults(
        should_add_value=AcceptValueNamed_a)
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'b', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])

    results.WillRunPage(self.pages[1])
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'd', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[1])
    results.PrintSummary()
    self.assertEquals(
        [('a', 'http://www.foo.com/'), ('a', 'http://www.bar.com/')],
        [(v.name, v.page.url) for v in results.all_page_specific_values])

  def testFilterValueWithImportHistogramDicts(self):
    def AcceptValueStartsWith_a(name, _):
      return name.startswith('a')
    hs = histogram_set.HistogramSet()
    hs.AddHistogram(histogram_module.Histogram('a', 'count'))
    hs.AddHistogram(histogram_module.Histogram('b', 'count'))
    results = self.getPageTestResults(
        should_add_value=AcceptValueStartsWith_a)
    results.WillRunPage(self.pages[0])
    results.ImportHistogramDicts(hs.AsDicts())
    results.DidRunPage(self.pages[0])

    new_hs = histogram_set.HistogramSet()
    new_hs.ImportDicts(results.AsHistogramDicts())
    self.assertEquals(len(new_hs), 1)

  def testFilterIsFirstResult(self):
    def AcceptSecondValues(_, is_first_result):
      return not is_first_result
    results = self.getPageTestResults(
        should_add_value=AcceptSecondValues)

    # First results (filtered out)
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 7,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'b', 'seconds', 8,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])
    results.WillRunPage(self.pages[1])
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 5,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'd', 'seconds', 6,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[1])

    # Second results
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'a', 'seconds', 3,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'b', 'seconds', 4,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[0])
    results.WillRunPage(self.pages[1])
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'a', 'seconds', 1,
        improvement_direction=improvement_direction.UP))
    results.AddValue(scalar.ScalarValue(
        self.pages[1], 'd', 'seconds', 2,
        improvement_direction=improvement_direction.UP))
    results.DidRunPage(self.pages[1])
    results.PrintSummary()
    expected_values = [
        ('a', 'http://www.foo.com/', 3),
        ('b', 'http://www.foo.com/', 4),
        ('a', 'http://www.bar.com/', 1),
        ('d', 'http://www.bar.com/', 2)]
    actual_values = [(v.name, v.page.url, v.value)
                     for v in results.all_page_specific_values]
    self.assertEquals(expected_values, actual_values)

  def testSkipValueCannotBeFiltered(self):
    def AcceptValueNamed_a(name, _):
      return name == 'a'
    results = self.getPageTestResults(
        should_add_value=AcceptValueNamed_a)
    results.WillRunPage(self.pages[0])
    results.AddValue(scalar.ScalarValue(
        self.pages[0], 'b', 'seconds', 8,
        improvement_direction=improvement_direction.UP))
    results.Skip('skip for testing')
    results.DidRunPage(self.pages[0])
    results.PrintSummary()

    # Although predicate says only accept value with named 'a', skip value is
    # added anyway.
    self.assertEquals(len(results.all_page_specific_values), 1)
    self.assertIsInstance(results.all_page_specific_values[0], skip.SkipValue)

  def testFilterHistogram(self):
    def AcceptValueNamed_a(name, _):
      return name.startswith('a')
    results = self.getPageTestResults(
        should_add_value=AcceptValueNamed_a)
    results.WillRunPage(self.pages[0])
    hist0 = histogram_module.Histogram('a', 'count')
    # Necessary to make sure avg is added
    hist0.AddSample(0)
    results.AddHistogram(hist0)
    hist1 = histogram_module.Histogram('b', 'count')
    hist1.AddSample(0)
    results.AddHistogram(hist1)

    # Filter out the diagnostics
    dicts = results.AsHistogramDicts()
    histogram_dicts = []
    for d in dicts:
      if 'name' in d:
        histogram_dicts.append(d)

    self.assertEquals(len(histogram_dicts), 1)
    self.assertEquals(histogram_dicts[0]['name'], 'a')

  def testFilterHistogram_AllStatsNotFiltered(self):
    def AcceptNonAverage(name, _):
      return not name.endswith('avg')
    results = self.getPageTestResults(
        should_add_value=AcceptNonAverage)
    results.WillRunPage(self.pages[0])
    hist0 = histogram_module.Histogram('a', 'count')
    # Necessary to make sure avg is added
    hist0.AddSample(0)
    results.AddHistogram(hist0)
    hist1 = histogram_module.Histogram('a_avg', 'count')
    # Necessary to make sure avg is added
    hist1.AddSample(0)
    results.AddHistogram(hist1)

    # Filter out the diagnostics
    dicts = results.AsHistogramDicts()
    histogram_dicts = []
    for d in dicts:
      if 'name' in d:
        histogram_dicts.append(d)

    self.assertEquals(len(histogram_dicts), 2)
    histogram_dicts.sort(key=lambda h: h['name'])

    self.assertEquals(len(histogram_dicts), 2)
    self.assertEquals(histogram_dicts[0]['name'], 'a')
    self.assertEquals(histogram_dicts[1]['name'], 'a_avg')

  @mock.patch('py_utils.cloud_storage.Insert')
  def testUploadArtifactsToCloud(self, cloud_storage_insert_patch):
    cs_path_name = 'https://cs_foo'
    cloud_storage_insert_patch.return_value = cs_path_name
    with tempfile_ext.NamedTemporaryDirectory(
        prefix='artifact_tests') as tempdir:

      ar = ar_module.ArtifactResults(tempdir)
      results = self.getPageTestResults(
          upload_bucket='abc', artifact_results=ar)


      with results.CreateArtifact('story1', 'screenshot') as screenshot1:
        pass

      with results.CreateArtifact('story2', 'log') as log2:
        pass

      results.UploadArtifactsToCloud()
      cloud_storage_insert_patch.assert_has_calls(
          [mock.call('abc', mock.ANY, screenshot1.name),
           mock.call('abc', mock.ANY, log2.name)],
          any_order=True)

      # Assert that the path is now the cloud storage path
      for _, artifacts in ar.IterTestAndArtifacts():
        for artifact_type in artifacts:
          for i, _ in enumerate(artifacts[artifact_type]):
            self.assertEquals(cs_path_name, artifacts[artifact_type][i])

  @mock.patch('py_utils.cloud_storage.Insert')
  def testUploadArtifactsToCloud_withNoOpArtifact(
      self, cloud_storage_insert_patch):
    del cloud_storage_insert_patch  # unused
    with tempfile_ext.NamedTemporaryDirectory(
        prefix='artifact_tests') as tempdir:

      ar = ar_module.NoopArtifactResults(tempdir)
      results = self.getPageTestResults(
          upload_bucket='abc', artifact_results=ar)


      with results.CreateArtifact('story1', 'screenshot'):
        pass

      with results.CreateArtifact('story2', 'log'):
        pass

      # Just make sure that this does not crash
      results.UploadArtifactsToCloud()
