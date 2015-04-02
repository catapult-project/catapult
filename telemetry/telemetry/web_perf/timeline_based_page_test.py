# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page_test

class TimelineBasedPageTest(page_test.PageTest):
  """Page test that collects metrics with TimelineBasedMeasurement."""
  def __init__(self, tbm):
    super(TimelineBasedPageTest, self).__init__('RunPageInteractions')
    self._measurement = tbm

  @property
  def measurement(self):
    return self._measurement

  def WillNavigateToPage(self, page, tab):
    tracing_controller = tab.browser.platform.tracing_controller
    self._measurement.WillRunUserStory(
        tracing_controller, page.GetSyntheticDelayCategories())

  def ValidateAndMeasurePage(self, page, tab, results):
    """Collect all possible metrics and added them to results."""
    tracing_controller = tab.browser.platform.tracing_controller
    self._measurement.Measure(tracing_controller, results)

  def CleanUpAfterPage(self, page, tab):
    tracing_controller = tab.browser.platform.tracing_controller
    self._measurement.DidRunUserStory(tracing_controller)
