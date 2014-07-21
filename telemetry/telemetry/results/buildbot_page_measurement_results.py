# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import perf_tests_helper
from telemetry import value as value_module
from telemetry.value import summary as summary_module
from telemetry.results import page_measurement_results


class BuildbotPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, output_stream, trace_tag=''):
    super(BuildbotPageMeasurementResults, self).__init__(output_stream)
    self._trace_tag = trace_tag

  def _PrintPerfResult(self, measurement, trace, v, units,
                       result_type='default'):
    output = perf_tests_helper.PrintPerfResult(
        measurement, trace, v, units, result_type, print_to_stdout=False)
    self._output_stream.write(output + '\n')
    self._output_stream.flush()

  @property
  def had_failures(self):
    return len(self.failures) > 0

  def PrintSummary(self):
    """Print summary data in a format expected by buildbot for perf dashboards.

    If any failed pages exist, only output individual page results, and do
    not output any average data.
    """
    # Print out the list of unique pages.
    perf_tests_helper.PrintPages(
        [page.display_name for page in self.pages_that_succeeded])
    summary = summary_module.Summary(self.all_page_specific_values,
                                     self.had_failures)
    for value in summary.interleaved_computed_per_page_values_and_summaries:
      if value.page:
        self._PrintComputedPerPageValue(value)
      else:
        self._PrintComputedSummaryValue(value)
    self._PrintOverallResults()

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

  def _PrintComputedSummaryValue(self, value):
    # If there were any page errors, we typically will print nothing.
    #
    # Note: this branch is structured less-densely to improve legibility.
    if self.had_failures:
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

  def _PrintOverallResults(self):
    # If there were no failed pages, output the overall results (results not
    # associated with a page).
    if not self.had_failures:
      for value in self.all_summary_values:
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
                          [len(self.failures)], 'count', 'unimportant')

    # TODO(chrishenry): Remove this in a separate patch to reduce the risk
    # of rolling back due to buildbot breakage.
    # Also fix src/tools/bisect-perf-regression_test.py when this is
    # removed.
    self._PrintPerfResult('telemetry_page_measurement_results', 'num_errored',
                          [0], 'count', 'unimportant')

    super(BuildbotPageMeasurementResults, self).PrintSummary()
