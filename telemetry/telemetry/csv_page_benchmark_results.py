# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page_benchmark_results import PageBenchmarkResults

class CsvPageBenchmarkResults(PageBenchmarkResults):
  def __init__(self, results_writer, output_after_every_page):
    super(CsvPageBenchmarkResults, self).__init__()
    self._results_writer = results_writer
    self._did_output_header = False
    self._header_names_written_to_writer = None
    self._output_after_every_page = output_after_every_page

  def DidMeasurePage(self):
    assert self.values_for_current_page, 'Failed to call WillMeasurePage'
    if not self._output_after_every_page:
      super(CsvPageBenchmarkResults, self).DidMeasurePage()
      return

    if not self._did_output_header:
      self._OutputHeader()
    else:
      self._ValidateOutputNamesForCurrentPage()

    self._OutputValuesForPage(self.values_for_current_page)

    super(CsvPageBenchmarkResults, self).DidMeasurePage()

  def PrintSummary(self, trace_tag):
    if not self._output_after_every_page:
      self._OutputHeader()
      for page_values in self.all_values_for_all_pages:
        self._OutputValuesForPage(page_values)

    super(CsvPageBenchmarkResults, self).PrintSummary(trace_tag)

  def _ValidateOutputNamesForCurrentPage(self):
    assert self._did_output_header
    current_page_measurement_names = \
        set(self.values_for_current_page.measurement_names)
    header_names_written_to_writer = \
        set(self._header_names_written_to_writer)
    if header_names_written_to_writer == current_page_measurement_names:
      return
    assert False, """To use CsvPageBenchmarkResults, you must add the same
result names for every page. In this case, first page output:
%s

Thus, all subsequent pages must output this as well. Instead, the current page
output:
%s

Change your test to produce the same thing each time, or modify
MultiPageBenchmark.results_are_the_same_on_every_page to return False.
""" % (repr(header_names_written_to_writer),
       repr(current_page_measurement_names))

  def _OutputHeader(self):
    assert not self._did_output_header
    all_measurement_names = list(
      self.all_measurements_that_have_been_seen.keys())
    all_measurement_names.sort()
    self._did_output_header = True
    self._header_names_written_to_writer = list(all_measurement_names)

    row = ['url']
    for measurement_name in all_measurement_names:
      measurement_data = \
          self.all_measurements_that_have_been_seen[measurement_name]
      row.append('%s (%s)' % (measurement_name, measurement_data['units']))
    self._results_writer.writerow(row)

  def _OutputValuesForPage(self, page_values):
    row = [page_values.page.url]
    for measurement_name in self._header_names_written_to_writer:
      value = page_values.FindValueByMeasurementName(measurement_name)
      if value:
        row.append('%s' % value.output_value)
      else:
        row.append('-')
    self._results_writer.writerow(row)
