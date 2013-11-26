# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from telemetry import value as value_module
from telemetry.page import page_measurement_results
from telemetry.page import perf_tests_helper
from telemetry.value import merge_values


class BuildbotPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, trace_tag=''):
    super(BuildbotPageMeasurementResults, self).__init__()
    self._trace_tag = trace_tag

  def _PrintPerfResult(self, measurement, trace, v, units,
                       result_type='default'):
    perf_tests_helper.PrintPerfResult(
        measurement, trace, v, units, result_type)

  def PrintSummary(self):
    """Print summary data in a format expected by buildbot for perf dashboards.

    If any failed pages exist, only output individual page results for
    non-failing pages, and do not output any average data.
    """
    # Print out the list of unique pages.
    perf_tests_helper.PrintPages(
      [page.display_name for page in self.pages_that_succeeded])
    self._PrintPerPageResults()
    self._PrintOverallResults()

  @property
  def had_errors_or_failures(self):
    return self.errors or self.failures

  def _PrintPerPageResults(self):
    all_successful_page_values = (
        self.GetAllPageSpecificValuesForSuccessfulPages())

    # We will later need to determine how many values were originally created
    # for each value name, to apply a workaround meant to clean up the printf
    # output.
    num_successful_pages_for_value_name = defaultdict(int)
    for v in all_successful_page_values:
      num_successful_pages_for_value_name[v.name] += 1

    # By here, due to page repeat options, all_values_from_successful_pages
    # contains values of the same name not only from mulitple pages, but also
    # from the same name. So even if, for instance, only one page ran, it may
    # have run twice, producing two 'x' values.
    #
    # So, get rid of the repeated pages by merging.
    merged_page_values = merge_values.MergeLikeValuesFromSamePage(
        all_successful_page_values)

    # Now we have a bunch of values, but there is only one value_name per page.
    # Suppose page1 and page2 ran, producing values x and y. We want to print
    #    x_by_url for page1
    #    x_by_url for page2
    #    x for page1, page2 combined
    #
    #    y_by_url for page1
    #    y_by_url for page2
    #    y for page1, page2 combined
    #
    # We already have the x_by_url values in the values array. But, we will need
    # them indexable by the value name.
    #
    # The following dict maps value_name -> list of pages that have values of
    # that name.
    per_page_values_by_value_name = defaultdict(list)
    for value in merged_page_values:
      per_page_values_by_value_name[value.name].append(value)

    # We already have the x_by_url values in the values array. But, we also need
    # the values merged across the pages. And, we will need them indexed by
    # value name so that we can find them when printing out value names in
    # alphabetical order.
    merged_pages_value_by_value_name = {}
    for value in merge_values.MergeLikeValuesFromDifferentPages(
        all_successful_page_values):
      assert value.name not in merged_pages_value_by_value_name
      merged_pages_value_by_value_name[value.name] = value

    # sorted_value names will govern the order we start printing values.
    value_names = set([v.name for v in merged_page_values])
    sorted_value_names = sorted(value_names)

    # Time to walk through the values by name, printing first the by_url values
    # and then the merged_site value.
    for value_name in sorted_value_names:
      per_page_values = per_page_values_by_value_name.get(value_name, [])

      # Sort the values by their url
      sorted_per_page_values = list(per_page_values)
      sorted_per_page_values.sort(
          key=lambda per_page_values: per_page_values.page.display_name)

      # Output the _by_url results.
      num_successful_pages_for_this_value_name = (
          num_successful_pages_for_value_name[value_name])
      for per_page_value in sorted_per_page_values:
        self._PrintPerPageValue(per_page_value,
                                num_successful_pages_for_this_value_name)

      # Output the combined values.
      merged_pages_value = merged_pages_value_by_value_name.get(value_name,
                                                                None)
      if merged_pages_value:
        self._PrintMergedPagesValue(merged_pages_value)

  def _PrintPerPageValue(self, value, num_successful_pages_for_this_value_name):
    # We dont print per-page-values when there is a trace tag.
    if self._trace_tag:
      return

    # If there were any page errors, we typically will print nothing.
    #
    # Note: this branch is structured less-densely to improve legibility.
    if num_successful_pages_for_this_value_name > 1:
      should_print = True
    elif (self.had_errors_or_failures and
         num_successful_pages_for_this_value_name == 1):
      should_print = True
    else:
      should_print = False

    if not should_print:
      return

    # Actually print the result.
    buildbot_value = value.GetBuildbotValue()
    buildbot_data_type = value.GetBuildbotDataType(
        output_context=value_module.PER_PAGE_RESULT_OUTPUT_CONTEXT)
    buildbot_measurement_name, buildbot_trace_name = (
        value.GetBuildbotMeasurementAndTraceNameForPerPageResult())
    self._PrintPerfResult(buildbot_measurement_name,
                          buildbot_trace_name,
                          buildbot_value, value.units, buildbot_data_type)

  def _PrintMergedPagesValue(self, value):
    # If there were any page errors, we typically will print nothing.
    #
    # Note: this branch is structured less-densely to improve legibility.
    if self.had_errors_or_failures:
      return

    buildbot_value = value.GetBuildbotValue()
    buildbot_data_type = value.GetBuildbotDataType(
        output_context=value_module.MERGED_PAGES_RESULT_OUTPUT_CONTEXT)
    buildbot_measurement_name, buildbot_trace_name = (
        value.GetBuildbotMeasurementAndTraceNameForMergedPagesResult(
            self._trace_tag))

    self._PrintPerfResult(buildbot_measurement_name,
                          buildbot_trace_name,
                          buildbot_value, value.units, buildbot_data_type)

  def _PrintOverallResults(self):
    # If there were no failed pages, output the overall results (results not
    # associated with a page).
    if not self.had_errors_or_failures:
      for value in self._all_summary_values:
        buildbot_value = value.GetBuildbotValue()
        buildbot_data_type = value.GetBuildbotDataType(
            output_context=value_module.SUMMARY_RESULT_OUTPUT_CONTEXT)
        buildbot_measurement_name, buildbot_trace_name = (
            value.GetBuildbotMeasurementAndTraceNameForMergedPagesResult(
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
    self._PrintPerfResult('telemetry_page_measurement_results', 'num_errored',
                          [len(self.errors)], 'count', 'unimportant')

    super(BuildbotPageMeasurementResults, self).PrintSummary()
