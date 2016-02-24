# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from profile_chrome import controllers_unittest
from profile_chrome import systrace_controller


class SystraceControllerTest(controllers_unittest.BaseControllerTest):
  def testGetCategories(self):
    categories = \
        systrace_controller.SystraceController.GetCategories(self.device)
    self.assertTrue(categories)
    assert 'gfx' in ' '.join(categories)

  def testTracing(self):
    categories = ['gfx', 'input', 'view']
    ring_buffer = False
    controller = systrace_controller.SystraceController(self.device,
                                                        categories,
                                                        ring_buffer)

    interval = 1
    try:
      controller.StartTracing(interval)
    finally:
      controller.StopTracing()
    result = controller.PullTrace()

    self.assertFalse(controller.IsTracingOn())
    try:
      with open(result) as f:
        self.assertTrue('CPU#' in f.read())
    finally:
      os.remove(result)
