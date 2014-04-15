# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.core.timeline import async_slice


class ParseTests(unittest.TestCase):
  def testParse(self):
    self.assertTrue(tir_module.IsTimelineInteractionRecord(
        'Interaction.Foo'))
    self.assertTrue(tir_module.IsTimelineInteractionRecord(
        'Interaction.Foo/Bar'))
    self.assertFalse(tir_module.IsTimelineInteractionRecord(
        'SomethingRandom'))

  def CreateRecord(self, event_name):
    s = async_slice.AsyncSlice(
      'cat', event_name,
      timestamp=1, duration=2)
    return tir_module.TimelineInteractionRecord.FromEvent(s)

  def testCreate(self):
    r = self.CreateRecord('Interaction.LogicalName')
    self.assertEquals('LogicalName', r.logical_name)
    self.assertEquals(False, r.is_smooth)
    self.assertEquals(False, r.is_loading_resources)

    r = self.CreateRecord('Interaction.LogicalName/is_smooth')
    self.assertEquals('LogicalName', r.logical_name)
    self.assertEquals(True, r.is_smooth)
    self.assertEquals(False, r.is_loading_resources)

    r = self.CreateRecord('Interaction.LogicalNameWith/Slash/is_smooth')
    self.assertEquals('LogicalNameWith/Slash', r.logical_name)
    self.assertEquals(True, r.is_smooth)
    self.assertEquals(False, r.is_loading_resources)

    r = self.CreateRecord(
        'Interaction.LogicalNameWith/Slash/is_smooth,is_loading_resources')
    self.assertEquals('LogicalNameWith/Slash', r.logical_name)
    self.assertEquals(True, r.is_smooth)
    self.assertEquals(True, r.is_loading_resources)

  def testGetJavascriptMarker(self):
    smooth_marker = tir_module.TimelineInteractionRecord.GetJavascriptMarker(
      'LogicalName', [tir_module.IS_SMOOTH])
    self.assertEquals('Interaction.LogicalName/is_smooth', smooth_marker)
    slr_marker = tir_module.TimelineInteractionRecord.GetJavascriptMarker(
      'LogicalName', [tir_module.IS_SMOOTH, tir_module.IS_LOADING_RESOURCES])
    self.assertEquals('Interaction.LogicalName/is_smooth,is_loading_resources',
                      slr_marker)

