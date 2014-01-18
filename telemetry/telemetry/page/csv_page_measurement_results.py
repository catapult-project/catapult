# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv

from telemetry.page import page_measurement_results
from telemetry.value import merge_values

class CsvPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, output_stream, output_after_every_page=None):
    super(CsvPageMeasurementResults, self).__init__(output_stream)
    self._results_writer = csv.writer(self._output_stream)
    self._did_output_header = False
    self._header_names_written_to_writer = None
    self._output_after_every_page = output_after_every_page

  def DidMeasurePage(self):
    try:
      assert self.page_specific_values_for_current_page != None

      values = self.page_specific_values_for_current_page
      if not values or not self._output_after_every_page:
        # Do not output if no results were added on this page or if output flag
        # is not set.
        return

      if not self._did_output_header:
        self._OutputHeader()
      else:
        self._ValidateOutputNamesForCurrentPage()
      self._OutputValuesForPage(values[0].page, values)
    finally:
      super(CsvPageMeasurementResults, self).DidMeasurePage()

  def PrintSummary(self):
    try:
      if self._output_after_every_page:
        return

      self._OutputHeader()
      values = merge_values.MergeLikeValuesFromSamePage(
          self.all_page_specific_values)
      value_groups_by_page = merge_values.GroupStably(
          values, lambda value: value.page.url)
      for values_for_page in value_groups_by_page:
        self._OutputValuesForPage(values_for_page[0].page, values_for_page)
    finally:
      super(CsvPageMeasurementResults, self).PrintSummary()

  def _ValidateOutputNamesForCurrentPage(self):
    assert self._did_output_header
    current_page_value_names = set([
      value.name for value in self.page_specific_values_for_current_page])
    header_names_written_to_writer = set(self._header_names_written_to_writer)
    assert header_names_written_to_writer >= current_page_value_names, \
        """To use CsvPageMeasurementResults, you must add the same
result names for every page. In this case, the following extra results were
added:
%s
""" % (current_page_value_names - header_names_written_to_writer)

  def _OutputHeader(self):
    assert not self._did_output_header
    all_value_names = list(
      self.all_value_names_that_have_been_seen)
    all_value_names.sort()
    self._did_output_header = True
    self._header_names_written_to_writer = list(all_value_names)

    row = ['page_name']
    for value_name in all_value_names:
      units = self.GetUnitsForValueName(value_name)
      row.append('%s (%s)' % (value_name, units))
    self._results_writer.writerow(row)
    self._output_stream.flush()

  def _OutputValuesForPage(self, page, page_values):
    row = [page.display_name]
    values_by_value_name = {}
    for value in page_values:
      values_by_value_name[value.name] = value

    for value_name in self._header_names_written_to_writer:
      value = values_by_value_name.get(value_name, None)
      if value and value.GetRepresentativeNumber():
        row.append('%s' % value.GetRepresentativeNumber())
      else:
        row.append('-')
    self._results_writer.writerow(row)
    self._output_stream.flush()
