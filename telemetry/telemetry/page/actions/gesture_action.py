# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action

class GestureAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(GestureAction, self).__init__(attributes)

  def RunAction(self, page, tab, previous_action):
    tab.ExecuteJavaScript(
        'console.time("' + self.GetTimelineMarkerName() + '")')

    self.RunGesture(page, tab, previous_action)

    tab.ExecuteJavaScript(
        'console.timeEnd("' + self.GetTimelineMarkerName() + '")')

  def RunGesture(self, page, tab, previous_action):
    raise NotImplementedError()

  def CustomizeBrowserOptions(self, options):
    options.AppendExtraBrowserArgs('--enable-gpu-benchmarking')
