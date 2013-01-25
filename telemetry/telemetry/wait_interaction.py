# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import time

from telemetry import page_interaction

class WaitInteraction(page_interaction.PageInteraction):
  def __init__(self, attributes=None):
    super(WaitInteraction, self).__init__(attributes)

  def RunInteraction(self, page, tab):
    assert hasattr(self, 'duration')
    time.sleep(self.duration)
