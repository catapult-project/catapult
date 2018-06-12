# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import legacy_page_test


class TimelineBasedPageTest(legacy_page_test.LegacyPageTest):
  """Page test that collects metrics with TimelineBasedMeasurement.

  WillRunStory(), Measure() and DidRunStory() are all done in story_runner
  explicitly. We still need this wrapper around LegacyPageTest because it
  executes some browser related functions (mainly TabForPage) in the parent
  class.

  TODO(crbug.com/851948): This class is due to be removed.
  """
  def __init__(self):
    super(TimelineBasedPageTest, self).__init__()

  def ValidateAndMeasurePage(self, page, tab, results):
    """Collect all possible metrics and added them to results."""
    # Measurement is done explicitly in story_runner for timeline based page
    # test.
    pass
