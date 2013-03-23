# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.core import util
from telemetry.core.chrome import inspector_timeline
from telemetry.test import tab_test_case

_SAMPLE_MESSAGE = {
  'children': [
    {'data': {},
     'startTime': 1352783525921.823,
     'type': 'BeginFrame',
     'usedHeapSize': 1870736},
    {'children': [],
     'data': {'height': 723,
              'width': 1272,
              'x': 0,
              'y': 0},
     'endTime': 1352783525921.8992,
     'frameId': '10.2',
     'startTime': 1352783525921.8281,
     'type': 'Layout',
     'usedHeapSize': 1870736},
    {'children': [
        {'children': [],
         'data': {'imageType': 'PNG'},
         'endTime': 1352783525927.7939,
         'startTime': 1352783525922.4241,
         'type': 'DecodeImage',
         'usedHeapSize': 1870736}
        ],
     'data': {'height': 432,
              'width': 1272,
              'x': 0,
              'y': 8},
     'endTime': 1352783525927.9822,
     'frameId': '10.2',
     'startTime': 1352783525921.9292,
     'type': 'Paint',
     'usedHeapSize': 1870736}
    ],
  'data': {},
  'endTime': 1352783525928.041,
  'startTime': 1352783525921.8049,
  'type': 'Program'}

class InspectorEventParsingTest(unittest.TestCase):
  def testParsingWithSampleData(self):
    root_event = inspector_timeline.InspectorTimeline.RawEventToTimelineEvent(
        _SAMPLE_MESSAGE)
    self.assertTrue(root_event)
    decode_image_event = [
      child for child in root_event.GetAllChildrenRecursive()
      if child.name == 'DecodeImage'][0]
    self.assertEquals(decode_image_event.args['data']['imageType'], 'PNG')
    self.assertTrue(decode_image_event.duration_ms > 0)

  def testParsingWithSimpleData(self):
    raw_event = {'type': 'Foo',
                 'startTime': 1,
                 'endTime': 3,
                 'children': []}
    event = inspector_timeline.InspectorTimeline.RawEventToTimelineEvent(
        raw_event)
    self.assertEquals('Foo', event.name)
    self.assertEquals(1, event.start_time_ms)
    self.assertEquals(3, event.end_time_ms)
    self.assertEquals(2, event.duration_ms)
    self.assertEquals([], event.children)

  def testParsingWithArgs(self):
    raw_event = {'type': 'Foo',
                 'startTime': 1,
                 'endTime': 3,
                 'foo': 7,
                 'bar': {'x': 1}}
    event = inspector_timeline.InspectorTimeline.RawEventToTimelineEvent(
        raw_event)
    self.assertEquals('Foo', event.name)
    self.assertEquals(1, event.start_time_ms)
    self.assertEquals(3, event.end_time_ms)
    self.assertEquals(2, event.duration_ms)
    self.assertEquals([], event.children)
    self.assertEquals(7, event.args['foo'])
    self.assertEquals(1, event.args['bar']['x'])

  def testEventsWithNoStartTimeAreDropped(self):
    raw_event = {'type': 'Foo',
                 'endTime': 1,
                 'children': []}
    event = inspector_timeline.InspectorTimeline.RawEventToTimelineEvent(
        raw_event)
    self.assertEquals(None, event)

  def testEventsWithNoEndTimeAreDropped(self):
    raw_event = {'type': 'Foo',
                 'endTime': 1,
                 'children': []}
    event = inspector_timeline.InspectorTimeline.RawEventToTimelineEvent(
        raw_event)
    self.assertEquals(None, event)


class InspectorTimelineTabTest(tab_test_case.TabTestCase):
  def _StartServer(self):
    base_dir = os.path.dirname(__file__)
    self._browser.SetHTTPServerDirectories(os.path.join(base_dir, '..', '..',
        'unittest_data'))

  def _WaitForAnimationFrame(self):
    def _IsDone():
      js_is_done = """done"""
      return bool(self._tab.EvaluateJavaScript(js_is_done))
    util.WaitFor(_IsDone, 5)

  def testGotTimeline(self):
    with inspector_timeline.InspectorTimeline.Recorder(self._tab):
      self._tab.ExecuteJavaScript(
"""
var done = false;
window.webkitRequestAnimationFrame(function() { done = true; });
""")
      self._WaitForAnimationFrame()

    r = self._tab.timeline_model.GetAllOfName('FireAnimationFrame')
    self.assertTrue(len(r) > 0)
    self.assertTrue(r[0].duration_ms > 0)
