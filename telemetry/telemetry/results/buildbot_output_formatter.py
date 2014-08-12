# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import perf_tests_helper
from telemetry import value as value_module
from telemetry.results import output_formatter
from telemetry.value import summary as summary_module


class BuildbotOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, trace_tag=''):
    super(BuildbotOutputFormatter, self).__init__(output_stream)
    self._trace_tag = trace_tag

  def _PrintPerfResult(self, measurement, trace, v, units,
                       result_type='default'):
    output = perf_tests_helper.PrintPerfResult(
        measurement, trace, v, units, result_type, print_to_stdout=False)
    self.output_stream.write(output + '\n')
    self.output_stream.flush()

  def Format(self, page_test_results):
    """Print summary data in a format expected by buildbot for perf dashboards.

    If any failed pages exist, only output individual page results, and do
    not output any average data.
    """
    had_failures = len(page_test_results.failures) > 0

    # Print out the list of unique pages.
    perf_tests_helper.PrintPages(
        [page.display_name for page in page_test_results.pages_that_succeeded])
    summary = summary_module.Summary(page_test_results.all_page_specific_values,
                                     had_failures)
    for value in summary.interleaved_computed_per_page_values_and_summaries:
      if value.page:
        self._PrintComputedPerPageValue(value)
      else:
        self._PrintComputedSummaryValue(value, had_failures)
    self._PrintOverallResults(page_test_results)

  def _PrintComputedPerPageValue(self, value):
    # We dont print per-page-values when there is a trace tag.
    if self._trace_tag:
      return

    # Actually print the result.
    buildbot_value = value.GetBuildbotValue()
    buildbot_data_type = value.GetBuildbotDataType(
        output_context=value_module.PER_PAGE_RESULT_OUTPUT_CONTEXT)
    if buildbot_value is None or buildbot_data_type is None:
      return

    buildbot_measurement_name, buildbot_trace_name = (
        value.GetBuildbotMeasurementAndTraceNameForPerPageResult())
    self._PrintPerfResult(buildbot_measurement_name,
                          buildbot_trace_name,
                          buildbot_value, value.units, buildbot_data_type)

  def _PrintComputedSummaryValue(self, value, had_failures):
    # If there were any page errors, we typically will print nothing.
    #
    # Note: this branch is structured less-densely to improve legibility.
    if had_failures:
      return

    buildbot_value = value.GetBuildbotValue()
    buildbot_data_type = value.GetBuildbotDataType(
        output_context=value_module.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT)
    if buildbot_value is None or buildbot_data_type is None:
      return

    buildbot_measurement_name, buildbot_trace_name = (
        value.GetBuildbotMeasurementAndTraceNameForComputedSummaryResult(
            self._trace_tag))
    self._PrintPerfResult(buildbot_measurement_name,
                          buildbot_trace_name,
                          buildbot_value, value.units, buildbot_data_type)

  def _PrintOverallResults(self, page_test_results):
    # If there were no failed pages, output the overall results (results not
    # associated with a page).
    had_failures = len(page_test_results.failures) > 0
    if not had_failures:
      for value in page_test_results.all_summary_values:
        buildbot_value = value.GetBuildbotValue()
        buildbot_data_type = value.GetBuildbotDataType(
            output_context=value_module.SUMMARY_RESULT_OUTPUT_CONTEXT)
        buildbot_measurement_name, buildbot_trace_name = (
            value.GetBuildbotMeasurementAndTraceNameForComputedSummaryResult(
                self._trace_tag))
        self._PrintPerfResult(
            buildbot_measurement_name,
            buildbot_trace_name,
            buildbot_value,
            value.units,
            buildbot_data_type)

    # Print the number of failed and errored pages.
    self._PrintPerfResult('telemetry_page_measurement_results', 'num_failed',
                          [len(page_test_results.failures)], 'count',
                          'unimportant')

    # TODO(chrishenry): Remove this in a separate patch to reduce the risk
    # of rolling back due to buildbot breakage.
    # Also fix src/tools/bisect-perf-regression_test.py when this is
    # removed.
    self._PrintPerfResult('telemetry_page_measurement_results', 'num_errored',
                          [0], 'count', 'unimportant')
