# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import logging
import unittest

from telemetry.core import util
from telemetry.timeline import trace_data

class TraceDataTest(unittest.TestCase):
  def testSerialize(self):
    ri = trace_data.TraceData({'traceEvents': [1,2,3]})
    f = cStringIO.StringIO()
    ri.Serialize(f)
    d = f.getvalue()

    self.assertIn('traceEvents', d)
    self.assertIn('[1, 2, 3]', d)

    json.loads(d)

  def testValidateWithNonPrimativeRaises(self):
    with self.assertRaises(trace_data.NonSerializableTraceData):
      trace_data.TraceData({'hello': TraceDataTest})

  def testValidateWithCircularReferenceRaises(self):
    a = []
    d = {'foo': a}
    a.append(d)
    with self.assertRaises(trace_data.NonSerializableTraceData):
      trace_data.TraceData(d)

  def testEmptyArrayValue(self):
    # We can import empty lists and empty string.
    d = trace_data.TraceData([])
    self.assertFalse(d.HasEventsFor(trace_data.CHROME_TRACE_PART))

  def testEmptyStringValue(self):
    d = trace_data.TraceData('')
    self.assertFalse(d.HasEventsFor(trace_data.CHROME_TRACE_PART))

  def testListForm(self):
    d = trace_data.TraceData([{'ph': 'B'}])
    self.assertTrue(d.HasEventsFor(trace_data.CHROME_TRACE_PART))
    self.assertEquals(1, len(d.GetEventsFor(trace_data.CHROME_TRACE_PART)))

  def testStringForm(self):
    d = trace_data.TraceData('[{"ph": "B"}]')
    self.assertTrue(d.HasEventsFor(trace_data.CHROME_TRACE_PART))
    self.assertEquals(1, len(d.GetEventsFor(trace_data.CHROME_TRACE_PART)))

  def testStringForm2(self):
    d = trace_data.TraceData('{"inspectorTimelineEvents": [1]}')
    self.assertTrue(d.HasEventsFor(trace_data.INSPECTOR_TRACE_PART))
    self.assertEquals(1, len(d.GetEventsFor(trace_data.INSPECTOR_TRACE_PART)))

  def testCorrectlyMalformedStringForm(self):
    d = trace_data.TraceData("""[
      {"ph": "B"}""")
    self.assertTrue(d.HasEventsFor(trace_data.CHROME_TRACE_PART))

  def testCorrectlyMalformedStringForm2(self):
    d = trace_data.TraceData("""[
      {"ph": "B"},""")
    self.assertTrue(d.HasEventsFor(trace_data.CHROME_TRACE_PART))

class TraceDataBuilderTest(unittest.TestCase):
  def testBasicChrome(self):
    builder = trace_data.TraceDataBuilder()
    builder.AddEventsTo(trace_data.CHROME_TRACE_PART, [1,2,3])
    builder.AddEventsTo(trace_data.TAB_ID_PART, ['tab-7'])

    d = builder.AsData()
    self.assertTrue(d.HasEventsFor(trace_data.CHROME_TRACE_PART))
    self.assertTrue(d.HasEventsFor(trace_data.TAB_ID_PART))

    self.assertRaises(Exception, builder.AsData)
