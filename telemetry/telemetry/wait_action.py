# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import time

from telemetry import page_action

class WaitAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(WaitAction, self).__init__(attributes)

  def RunAction(self, page, tab):
    assert hasattr(self, 'duration')
    time.sleep(self.duration)
