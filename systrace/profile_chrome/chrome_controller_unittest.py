# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import json

from profile_chrome import chrome_controller
from profile_chrome import controllers_unittest


class ChromeControllerTest(controllers_unittest.BaseControllerTest):
  def testGetCategories(self):
    categories = \
        chrome_controller.ChromeTracingController.GetCategories(
            self.device, self.package_info)

    self.assertEquals(len(categories), 2)
    self.assertTrue(categories[0])
    self.assertTrue(categories[1])

  def testTracing(self):
    categories = '*'
    ring_buffer = False
    controller = chrome_controller.ChromeTracingController(self.device,
                                                           self.package_info,
                                                           categories,
                                                           ring_buffer)

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
