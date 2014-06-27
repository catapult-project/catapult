# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.page.actions import page_action

class RepaintContinuouslyAction(page_action.PageAction):
  """ Continuously repaints the visible content by requesting animation frames
  until self.seconds have elapsed AND at least three RAFs have been fired. Times
  out after max(60, self.seconds), if less than three RAFs were fired.
  """
  def __init__(self, seconds):
    super(RepaintContinuouslyAction, self).__init__()
    self._seconds = seconds

  def RunAction(self, tab):
    start_time = time.time()
    tab.ExecuteJavaScript(
        'window.__rafCount = 0;'
        'window.__rafFunction = function() {'
          'window.__rafCount += 1;'
          'window.webkitRequestAnimationFrame(window.__rafFunction);'
        '};'
        'window.webkitRequestAnimationFrame(window.__rafFunction);')

    time_out = max(60, self._seconds)
    min_rafs = 3

    # Wait until at least self.seconds have elapsed AND min_rafs have
    # been fired.  Use a hard time-out after 60 seconds (or
    # self.seconds).
    while True:
      raf_count = tab.EvaluateJavaScript('window.__rafCount;')
      elapsed_time = time.time() - start_time
      if elapsed_time > time_out:
        break
      elif elapsed_time > self._seconds and raf_count > min_rafs:
        break
      time.sleep(1)
