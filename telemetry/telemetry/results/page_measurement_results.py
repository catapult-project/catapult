# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module
from telemetry.results import page_test_results
from telemetry.value import value_backcompat

class PageMeasurementResults(page_test_results.PageTestResults):
  def __init__(self, output_stream=None, trace_tag=''):
    super(PageMeasurementResults, self).__init__(output_stream)
    self._done = False
    self._trace_tag = trace_tag

    self._current_page = None
    self._page_specific_values_for_current_page = None

    self._representative_value_for_each_value_name = {}

    self._all_summary_values = []
    self._all_page_specific_values = []

  @property
  def pages_that_succeeded(self):
    pages = set([value.page for value in self._all_page_specific_values])
    pages.difference_update(self.pages_that_had_errors_or_failures)
    return pages

  @property
  def current_page(self):
    return self._current_page

  @property
  def all_page_specific_values(self):
    return self._all_page_specific_values

  @property
  def page_specific_values_for_current_page(self):
    assert self._current_page
    return self._page_specific_values_for_current_page

  def WillMeasurePage(self, page):
    assert not self._current_page
    self._current_page = page
    self._page_specific_values_for_current_page = []

  def Add(self, trace_name, units, value, chart_name=None, data_type='default'):
    # TODO(isherman): Remove this as well.
    value = value_backcompat.ConvertOldCallingConventionToValue(
      self._current_page,
      trace_name, units, value, chart_name, data_type)
    self.AddValue(value)

  def AddValue(self, value):
    self._ValidateValue(value)
    self._page_specific_values_for_current_page.append(value)
    self._all_page_specific_values.append(value)

  def AddSummaryValue(self, value):
    assert value.page is None
    self._ValidateValue(value)
    self._all_summary_values.append(value)

  def _ValidateValue(self, value):
    assert isinstance(value, value_module.Value)
    if value.name not in self._representative_value_for_each_value_name:
      self._representative_value_for_each_value_name[value.name] = value
    representative_value = self._representative_value_for_each_value_name[
        value.name]
    assert value.IsMergableWith(representative_value)

  def DidMeasurePage(self):
    assert self._current_page, 'Failed to call WillMeasurePage'
    self._current_page = None
    self._page_specific_values_for_current_page = None


  def FindPageSpecificValuesForPage(self, page, value_name):
    values = []
    for value in self._all_page_specific_values:
      if value.page == page and value.name == value_name:
        values.append(value)
    return values


  def FindAllPageSpecificValuesNamed(self, value_name):
    values = []
    for value in self._all_page_specific_values:
      if value.name == value_name:
        values.append(value)
    return values
