# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import legacy_page_test


class TimelineBasedPageTest(legacy_page_test.LegacyPageTest):
  """Page test that collects metrics with TimelineBasedMeasurement.

  WillRunStory(), Measure() and DidRunStory() are all done in story_runner
  explicitly. For the moment we need this wrapper around LegacyPageTest to:
  - provide an empty implementation for ValidateAndMeasurePage (which is
    abstract in the parent class).
  - provide RunNavigateSteps (from the parent class), which is also deprecated
    and its code could be moved to the shared state.

  TODO(crbug.com/851948): This class is due to be removed.
  """
  def ValidateAndMeasurePage(self, page, tab, results):
    """Collect all possible metrics and added them to results."""
    # Measurement is done explicitly in story_runner for timeline based page
    # test.
    pass
