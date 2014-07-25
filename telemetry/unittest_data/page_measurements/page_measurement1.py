# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A simple PageMeasurement used by page/record_wpr.py's unit tests."""

from telemetry.page import page_measurement

class MockPageMeasurementOne(page_measurement.PageMeasurement):
  def __init__(self):
    super(MockPageMeasurementOne, self).__init__(action_name_to_run="RunFoo")

  def MeasurePage(self, page, tab, results):
    pass
