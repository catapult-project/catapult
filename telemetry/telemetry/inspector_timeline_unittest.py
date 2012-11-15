# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import inspector_timeline
from telemetry import tab_test_case
from telemetry import util


_SAMPLE_STREAM = [
{u'method': u'Timeline.eventRecorded',
  u'params': {u'record': {u'children': [
  {u'data': {},
   u'startTime': 1352783525921.823,
   u'type': u'BeginFrame',
   u'usedHeapSize': 1870736},
  {u'children': [],
   u'data': {u'height': 723,
             u'width': 1272,
             u'x': 0,
             u'y': 0},
   u'endTime': 1352783525921.8992,
   u'frameId': u'10.2',
   u'startTime': 1352783525921.8281,
   u'type': u'Layout',
   u'usedHeapSize': 1870736},
  {u'children': [{u'children': [],
                  u'data': {u'imageType': u'PNG'},
                  u'endTime': 1352783525927.7939,
                  u'startTime': 1352783525922.4241,
                  u'type': u'DecodeImage',
                  u'usedHeapSize': 1870736}],
   u'data': {u'height': 432,
             u'width': 1272,
             u'x': 0,
             u'y': 8},
   u'endTime': 1352783525927.9822,
   u'frameId': u'10.2',
   u'startTime': 1352783525921.9292,
   u'type': u'Paint',
   u'usedHeapSize': 1870736}],
u'data': {},
u'endTime': 1352783525928.041,
u'startTime': 1352783525921.8049,
u'type': u'Program'}}},
]


class InspectorTimelineTest(unittest.TestCase):
  def testTimelineEventParsing(self):
    timeline_events = inspector_timeline.TimelineEvents()
    for raw_events in _SAMPLE_STREAM:
      timeline_events.AppendRawEvents(raw_events)
    decode_image_events = timeline_events.GetAllOfType('DecodeImage')
    self.assertEquals(len(decode_image_events), 1)
    self.assertEquals(decode_image_events[0].data['imageType'], 'PNG')
    self.assertTrue(decode_image_events[0].elapsed_time > 0)


class InspectorTimelineTabTest(tab_test_case.TabTestCase):
  def _StartServer(self):
    base_dir = os.path.dirname(__file__)
    self._browser.SetHTTPServerDirectory(os.path.join(base_dir, '..',
        'unittest_data'))

  def _WaitForAnimationFrame(self):
    def _IsDone():
      js_is_done = """done"""
      return bool(self._tab.runtime.Evaluate(js_is_done))
    util.WaitFor(_IsDone, 5)

  def testGotTimeline(self):
    self._StartServer()
    image_url = self._browser.http_server.UrlOf('image.png')
    with inspector_timeline.InspectorTimeline.Recorder(self._tab.timeline):
      self._tab.runtime.Execute(
"""
var done = false;
var i = document.createElement('img');
i.src = '%s';
document.body.appendChild(i);
window.webkitRequestAnimationFrame(function() { done = true; });
""" % image_url)
      self._WaitForAnimationFrame()

    r = self._tab.timeline.timeline_events.GetAllOfType('DecodeImage')
    self.assertTrue(len(r) > 0)
    self.assertEquals(r[0].data['imageType'], 'PNG')
    self.assertTrue(r[0].elapsed_time > 0)
