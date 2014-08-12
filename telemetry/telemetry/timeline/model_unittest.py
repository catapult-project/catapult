# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import model
from telemetry.timeline import tracing_timeline_data


class TimelineModelUnittest(unittest.TestCase):
  def testEmptyImport(self):
    model.TimelineModel(
        tracing_timeline_data.TracingTimelineData([]))
    model.TimelineModel(
        tracing_timeline_data.TracingTimelineData(''))
