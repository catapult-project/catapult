# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.testing import tab_test_case
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options

class TracingControllerTest(tab_test_case.TabTestCase):

  @decorators.Isolated
  def testModifiedConsoleTime(self):
    category_filter = tracing_category_filter.TracingCategoryFilter()
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._tab.browser.platform.tracing_controller.Start(options,
                                                        category_filter)
    self.Navigate('blank.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')
    self._tab.EvaluateJavaScript('console.time = function() { };')
    with self.assertRaisesRegexp(Exception, 'Page stomped on console.time'):
      self._tab.browser.platform.tracing_controller.Stop()
