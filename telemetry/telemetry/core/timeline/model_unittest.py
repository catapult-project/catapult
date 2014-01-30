# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.timeline import model

class TimelineModelUnittest(unittest.TestCase):
  def testEmptyImport(self):
    model.TimelineModel([])
    model.TimelineModel('')
