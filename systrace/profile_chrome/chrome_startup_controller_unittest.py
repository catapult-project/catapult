# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import json

from profile_chrome import chrome_startup_controller
from profile_chrome import controllers_unittest


class ChromeControllerTest(controllers_unittest.BaseControllerTest):
  def testTracing(self):
    controller = chrome_startup_controller.ChromeStartupTracingController(
        self.device, self.package_info, False, 'https://www.google.com')

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
