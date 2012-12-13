# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
import os
import sys

from telemetry import page_test

# Get build/android/pylib scripts into our path.
# TODO(tonyg): Move perf_tests_helper.py to a common location.
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     '../../../build/android/pylib')))
# pylint: disable=F0401
from perf_tests_helper import GeomMeanAndStdDevFromHistogram
from perf_tests_helper import PrintPerfResult  # pylint: disable=F0401


def _Mean(l):
  return float(sum(l)) / len(l) if len(l) > 0 else 0.0


class MeasurementFailure(page_test.Failure):
  """Exception that can be thrown from MeasurePage to indicate an undesired but
  designed-for problem."""
  pass


class BenchmarkResults(page_test.PageTestResults):
  def __init__(self):
    super(BenchmarkResults, self).__init__()
    self.results_summary = defaultdict(list)
    self.page_results = []
    self.urls = []
    self.field_names = None
    self.field_units = {}
    self.field_types = {}

    self._page = None
    self._page_values = {}

  def WillMeasurePage(self, page):
    self._page = page
    self._page_values = {}

  def Add(self, trace_name, units, value, chart_name=None, data_type='default'):
    name = trace_name
    if chart_name:
      name = '%s.%s' % (chart_name, trace_name)
    assert name not in self._page_values, 'Result names must be unique'
    assert name != 'url', 'The name url cannot be used'
    if self.field_names:
      assert name in self.field_names, """MeasurePage returned inconsistent
results! You must return the same dict keys every time."""
    else:
      self.field_units[name] = units
      self.field_types[name] = data_type
    self._page_values[name] = value

  def DidMeasurePage(self):
    assert self._page, 'Failed to call WillMeasurePage'

    if not self.field_names:
      self.field_names = self._page_values.keys()
      self.field_names.sort()

    self.page_results.append(self._page_values)
    self.urls.append(self._page.display_url)
    for name in self.field_names:
      units = self.field_units[name]
      data_type = self.field_types[name]
      value = self._page_values[name]
      self.results_summary[(name, units, data_type)].append(value)

  def PrintSummary(self, trace_tag):
    if self.page_failures:
      return
    for measurement_units_type, values in sorted(
        self.results_summary.iteritems()):
      measurement, units, data_type = measurement_units_type
      if data_type == 'histogram':
        # For histograms, the _by_url data is important.
        by_url_data_type = 'histogram'
      else:
        # For non-histograms, the _by_url data is unimportant.
        by_url_data_type = 'unimportant'
      if '.' in measurement:
        measurement, trace = measurement.split('.', 1)
        trace += (trace_tag or '')
      else:
        trace = measurement + (trace_tag or '')
      if len(self.urls) > 1 and not trace_tag:
        print
        assert len(self.urls) == len(values)
        for i, value in enumerate(values):
          PrintPerfResult(measurement + '_by_url', self.urls[i], [value], units,
                          by_url_data_type)
      # For histograms, we don't print the average data, only the _by_url.
      if not data_type == 'histogram':
        PrintPerfResult(measurement, trace, values, units, data_type)


class IncrementalBenchmarkResults(BenchmarkResults):
  def __init__(self):
    super(IncrementalBenchmarkResults, self).__init__()
    self._did_process_header = False

  def DidMeasurePage(self):
    super(IncrementalBenchmarkResults, self).DidMeasurePage()

    if not self._did_process_header:
      self.ProcessHeader()

    row = [self._page.url]
    for name in self.field_names:
      value = self._page_values[name]
      if self.field_types[name] == 'histogram':
        avg, _ = GeomMeanAndStdDevFromHistogram(value)
        row.append(avg)
      elif isinstance(value, list):
        row.append(_Mean(value))
      else:
        row.append(value)
    self.OutputRow(row)

  def OutputRow(self, row):
    raise NotImplementedError()

  def ProcessHeader(self):
    raise NotImplementedError()

class CsvBenchmarkResults(IncrementalBenchmarkResults):
  def __init__(self, results_writer):
    super(CsvBenchmarkResults, self).__init__()
    self._results_writer = results_writer

  def OutputRow(self, row):
    self._results_writer.writerow(row)

  def ProcessHeader(self):
    self._did_process_header = True
    row = ['url']
    for name in self.field_names:
      row.append('%s (%s)' % (name, self.field_units[name]))
    self.OutputRow(row)

class TerminalBlockBenchmarkResults(IncrementalBenchmarkResults):
  def __init__(self, output_location):
    super(TerminalBlockBenchmarkResults, self).__init__()
    self._output_location = output_location
    self._header_row = None

  def OutputRow(self, row):
    for i in range(len(row)):
      print >> self._output_location, '%s:' % self._header_row[i], row[i]
    print >> self._output_location

  def ProcessHeader(self):
    self._did_process_header = True
    self._header_row = ['url']
    for name in self.field_names:
      self._header_row.append('%s (%s)' % (name, self.field_units[name]))


# TODO(nduca): Rename to page_benchmark
class MultiPageBenchmark(page_test.PageTest):
  """Glue code for running a benchmark across a set of pages.

  To use this, subclass from the benchmark and override MeasurePage. For
  example:

     class BodyChildElementBenchmark(MultiPageBenchmark):
        def MeasurePage(self, page, tab, results):
           body_child_count = tab.runtime.Evaluate(
               'document.body.children.length')
           results.Add('body_children', 'count', body_child_count)

     if __name__ == '__main__':
         multi_page_benchmark.Main(BodyChildElementBenchmark())

  All benchmarks should include a unit test!

     TODO(nduca): Add explanation of how to write the unit test.

  To add test-specific options:

     class BodyChildElementBenchmark(MultiPageBenchmark):
        def AddCommandLineOptions(parser):
           parser.add_option('--element', action='store', default='body')

        def MeasurePage(self, page, tab, results):
           body_child_count = tab.runtime.Evaluate(
              'document.querySelector('%s').children.length')
           results.Add('children', 'count', child_count)
  """
  def __init__(self, interaction_name=''):
    super(MultiPageBenchmark, self).__init__('_RunTest', interaction_name)

  def _RunTest(self, page, tab, results):
    results.WillMeasurePage(page)
    self.MeasurePage(page, tab, results)
    results.DidMeasurePage()

  def MeasurePage(self, page, tab, results):
    """Override to actually measure the page's performance.

    page is a page_set.Page
    tab is an instance of telemetry.Tab

    Should call results.Add(name, units, value) for each result, or raise an
    exception on failure. The name and units of each Add() call must be
    the same across all iterations. The name 'url' must not be used.

    Prefer field names that are in accordance with python variable style. E.g.
    field_name.

    Put together:

       def MeasurePage(self, page, tab, results):
         res = tab.runtime.Evaluate('2+2')
         if res != 4:
           raise Exception('Oh, wow.')
         results.Add('two_plus_two', 'count', res)
    """
    raise NotImplementedError()
