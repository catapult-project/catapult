#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys

from telemetry.page import page_measurement
from telemetry.page import page_test_runner

def Main(measurement_dir, profile_creators_dir, page_set_filenames):
  """Turns a PageMeasurement into a command-line program.

  Args:
    measurement_dir: Path to directory containing PageMeasurements.
    profile_creators_dir: Path to directory containing ProfileCreators.
  """
  runner = PageMeasurementRunner()
  sys.exit(runner.Run(
      measurement_dir, profile_creators_dir, page_set_filenames))

class PageMeasurementRunner(page_test_runner.PageTestRunner):
  @property
  def test_class(self):
    return page_measurement.PageMeasurement

  @property
  def test_class_name(self):
    return 'measurement'
