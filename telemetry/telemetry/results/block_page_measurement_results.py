# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.results import page_measurement_results
from telemetry.value import merge_values

class BlockPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, output_stream):
    super(BlockPageMeasurementResults, self).__init__(output_stream)

  def PrintSummary(self):
    try:
      values = merge_values.MergeLikeValuesFromSamePage(
          self.all_page_specific_values)
      value_groups_by_page = merge_values.GroupStably(
          values, lambda value: value.page.url)
      for values_for_page in value_groups_by_page:
        if not values_for_page:
          # Do not output if no results were added on this page.
          return
        lines = ['name: %s' % values_for_page[0].page.display_name]
        for value in sorted(values_for_page, key=lambda x: x.name):
          lines.append('%s (%s): %s' %
                       (value.name,
                        value.units,
                        value.GetRepresentativeString()))
        for line in lines:
          self._output_stream.write(line)
          self._output_stream.write(os.linesep)
        self._output_stream.write(os.linesep)
        self._output_stream.flush()
    finally:
      super(BlockPageMeasurementResults, self).PrintSummary()
