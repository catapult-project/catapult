# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry.results import page_measurement_results

class BlockPageMeasurementResults(
    page_measurement_results.PageMeasurementResults):
  def __init__(self, output_stream):
    super(BlockPageMeasurementResults, self).__init__(output_stream)

  def DidMeasurePage(self):
    try:
      values = self.page_specific_values_for_current_page
      if not values:
        # Do not output if no results were added on this page.
        return
      lines = ['name: %s' % values[0].page.display_name]
      for value in sorted(values, key=lambda x: x.name):
        if value.GetRepresentativeString() is not None:
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
      super(BlockPageMeasurementResults, self).DidMeasurePage()
