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
    values = self.page_specific_values_for_current_page
    if not values:
      # Do not output if no results were added on this page.
      super(BlockPageMeasurementResults, self).DidMeasurePage()
      return
    lines = ['name: %s' %
             values[0].page.display_name]

    for value in sorted(values, key=lambda x: x.name):
      lines.append('%s (%s): %s' %
                 (value.name,
                  value.units,
                  value.GetRepresentativeString()))
    for line in lines:
      self._output_file.write(line)
      self._output_file.write(os.linesep)
    self._output_file.write(os.linesep)
    self._output_file.flush()

    super(BlockPageMeasurementResults, self).DidMeasurePage()
