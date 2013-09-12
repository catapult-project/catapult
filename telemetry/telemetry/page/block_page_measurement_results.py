# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.page import page_measurement_results

class BlockPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, output_file):
    super(BlockPageMeasurementResults, self).__init__()
    self._output_file = output_file

  def DidMeasurePage(self):
    page_values = self.values_for_current_page

    if not page_values.values:
      # Do not output if no results were added on this page.
      super(BlockPageMeasurementResults, self).DidMeasurePage()
      return

    lines = ['name: %s' %
             self.values_for_current_page.page.display_name]
    sorted_measurement_names = page_values.measurement_names
    sorted_measurement_names.sort()

    for measurement_name in sorted_measurement_names:
      value = page_values.FindValueByMeasurementName(measurement_name)
      lines.append('%s (%s): %s' %
                 (measurement_name,
                  value.units,
                  value.output_value))
    for line in lines:
      self._output_file.write(line)
      self._output_file.write(os.linesep)
    self._output_file.write(os.linesep)
    self._output_file.flush()

    super(BlockPageMeasurementResults, self).DidMeasurePage()
