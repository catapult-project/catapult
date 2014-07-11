# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import benchmark
from telemetry.unittest import tab_test_case


class InspectorMemoryTest(tab_test_case.TabTestCase):

  @benchmark.Enabled('has tabs')
  def testGetDOMStats(self):
    # Due to an issue with CrOS, we create a new tab here rather than
    # using the existing tab to get a consistent starting page on all platforms.
    self._tab = self._browser.tabs.New()

    self.Navigate('dom_counter_sample.html')

    counts = self._tab.dom_stats
    self.assertEqual(counts['document_count'], 1)
    self.assertEqual(counts['node_count'], 14)
    self.assertEqual(counts['event_listener_count'], 2)
