# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from profile_chrome import controllers_unittest
from profile_chrome import ddms_controller


class DdmsControllerTest(controllers_unittest.BaseControllerTest):
  def testTracing(self):
    controller = ddms_controller.DdmsController(self.device, self.package_info)

    interval = 1
    try:
      controller.StartTracing(interval)
    finally:
      controller.StopTracing()

    result = controller.PullTrace()
    try:
      with open(result) as f:
        self.assertTrue(f.read().startswith('*version'))
    finally:
      os.remove(result)
