# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
from itertools import chain

from telemetry.page import page_test
from telemetry.page import perf_tests_helper
from telemetry.page import page_benchmark_value

class ValuesForSinglePage(object):
  def __init__(self, page):
    self.page = page
    self.values = []

  def AddValue(self, value):
    self.values.append(value)

  @property
  def measurement_names(self):
    return [value.measurement_name for value in self.values]

  def FindValueByMeasurementName(self, measurement_name):
    values = [value for value in self.values
              if value.measurement_name == measurement_name]
    assert len(values) <= 1
    if len(values):
      return values[0]
    return None

  def __getitem__(self, trace_name):
    return self.FindValueByTraceName(trace_name)

  def __contains__(self, trace_name):
    return self.FindValueByTraceName(trace_name) != None

  def FindValueByTraceName(self, trace_name):
    values = [value for value in self.values
              if value.trace_name == trace_name]
    assert len(values) <= 1
    if len(values):
      return values[0]
    return None

class PageBenchmarkResults(page_test.PageTestResults):
  def __init__(self):
    super(PageBenchmarkResults, self).__init__()
    self._page_results = []

    self._all_measurements_that_have_been_seen = {}

    self._values_for_current_page = {}

  def __getitem__(self, i):
    """Shorthand for self.page_results[i]"""
    return self._page_results[i]

  def __len__(self):
    return len(self._page_results)

  @property
  def values_for_current_page(self):
    return self._values_for_current_page

  @property
  def page_results(self):
    return self._page_results

  def WillMeasurePage(self, page):
    self._values_for_current_page = ValuesForSinglePage(page)

  @property
  def all_measurements_that_have_been_seen(self):
    return self._all_measurements_that_have_been_seen

  def Add(self, trace_name, units, value, chart_name=None, data_type='default'):
    value = page_benchmark_value.PageBenchmarkValue(
        trace_name, units, value, chart_name, data_type)
    measurement_name = value.measurement_name

    # Sanity checks.
    assert measurement_name != 'url', 'The name url cannot be used'
    if measurement_name in self._all_measurements_that_have_been_seen:
      measurement_data = \
          self._all_measurements_that_have_been_seen[measurement_name]
      last_seen_units = measurement_data['units']
      last_seen_data_type = measurement_data['type']
      assert last_seen_units == units, \
          'Unit cannot change for a name once it has been provided'
      assert last_seen_data_type == data_type, \
          'Unit cannot change for a name once it has been provided'
    else:
      self._all_measurements_that_have_been_seen[measurement_name] = {
        'units': units,
        'type': data_type}

    self._values_for_current_page.AddValue(value)

  def DidMeasurePage(self):
    assert self._values_for_current_page, 'Failed to call WillMeasurePage'
    self._page_results.append(self._values_for_current_page)
    self._values_for_current_page = None

  def _PrintPerfResult(self, measurement, trace, values, units,
                       result_type='default'):
    perf_tests_helper.PrintPerfResult(
        measurement, trace, values, units, result_type)

  def PrintSummary(self, trace_tag):
    if self.page_failures:
      return

    # Build the results summary.
    results_summary = defaultdict(list)
    for measurement_name in \
          self._all_measurements_that_have_been_seen.iterkeys():
      for page_values in self._page_results:
        value = page_values.FindValueByMeasurementName(measurement_name)
        if not value:
          continue
        measurement_units_type = (measurement_name,
                                  value.units,
                                  value.data_type)
        value_url = (value.value, page_values.page.display_url)
        results_summary[measurement_units_type].append(value_url)

    # Output the results summary sorted by name, then units, then data type.
    for measurement_units_type, value_url_list in sorted(
        results_summary.iteritems()):
      measurement, units, data_type = measurement_units_type

      if 'histogram' in data_type:
        by_url_data_type = 'unimportant-histogram'
      else:
        by_url_data_type = 'unimportant'
      if '.' in measurement and 'histogram' not in data_type:
        measurement, trace = measurement.split('.', 1)
        trace += (trace_tag or '')
      else:
        trace = measurement + (trace_tag or '')

      if not trace_tag and len(value_url_list) > 1:
        for value, url in value_url_list:
          self._PrintPerfResult(measurement + '_by_url', url, [value], units,
                                by_url_data_type)

      # For histograms, we don't print the average data, only the _by_url,
      # unless there is only 1 page in which case the _by_urls are omitted.
      if 'histogram' not in data_type or len(value_url_list) == 1:
        values = [i[0] for i in value_url_list]
        if isinstance(values[0], list):
          values = list(chain.from_iterable(values))
        self._PrintPerfResult(measurement, trace, values, units, data_type)
