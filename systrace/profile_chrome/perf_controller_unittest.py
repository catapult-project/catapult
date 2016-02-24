# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import json

from profile_chrome import controllers_unittest
from profile_chrome import perf_controller
from profile_chrome import ui


class PerfProfilerControllerTest(controllers_unittest.BaseControllerTest):
  def testGetCategories(self):
    if not perf_controller.PerfProfilerController.IsSupported():
      return
    categories = \
        perf_controller.PerfProfilerController.GetCategories(self.device)
    assert 'cycles' in ' '.join(categories)

  def testTracing(self):
    if not perf_controller.PerfProfilerController.IsSupported():
      return
    ui.EnableTestMode()
    categories = ['cycles']
    controller = perf_controller.PerfProfilerController(self.device,
                                                        categories)

    interval = 1
    try:
      controller.StartTracing(interval)
    finally:
      controller.StopTracing()

    result = controller.PullTrace()
    try:
      with open(result) as f:
        json.loads(f.read())
    finally:
      os.remove(result)
