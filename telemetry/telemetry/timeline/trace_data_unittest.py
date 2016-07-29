# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import datetime
import exceptions
import json
import os
import tempfile
import unittest
import zipfile

from telemetry.timeline import trace_data

class TraceDataTest(unittest.TestCase):
  def testSerialize(self):
    ri = trace_data.TraceData({'traceEvents': [1, 2, 3]})
    f = cStringIO.StringIO()
    ri.Serialize(f)
    d = f.getvalue()

    self.assertIn('traceEvents', d)
    self.assertIn('[1, 2, 3]', d)

    json.loads(d)

  def testSerializeZip(self):
    data = trace_data.TraceData({'traceEvents': [1, 2, 3],
                                 'powerTraceAsString': 'battor_data'})
    tf = tempfile.NamedTemporaryFile(delete=False)
    temp_name = tf.name
    tf.close()
    try:
      data.Serialize(temp_name, gzip_result=True)
      self.assertTrue(zipfile.is_zipfile(temp_name))
      z = zipfile.ZipFile(temp_name, 'r')

      self.assertIn('powerTraceAsString', z.namelist())
      self.assertIn('traceEvents', z.namelist())
      z.close()
    finally:
      os.remove(temp_name)

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
    self.assertFalse(d.HasTraceFor(trace_data.CHROME_TRACE_PART))

  def testEmptyStringValue(self):
    d = trace_data.TraceData('')
    self.assertFalse(d.HasTraceFor(trace_data.CHROME_TRACE_PART))

  def testListForm(self):
    d = trace_data.TraceData([{'ph': 'B'}])
    self.assertTrue(d.HasTraceFor(trace_data.CHROME_TRACE_PART))
    events = d.GetTraceFor(trace_data.CHROME_TRACE_PART).get('traceEvents', [])
    self.assertEquals(1, len(events))

  def testStringForm(self):
    d = trace_data.TraceData('[{"ph": "B"}]')
    self.assertTrue(d.HasTraceFor(trace_data.CHROME_TRACE_PART))
    events = d.GetTraceFor(trace_data.CHROME_TRACE_PART).get('traceEvents', [])
    self.assertEquals(1, len(events))

  def testStringForm2(self):
    d = trace_data.TraceData('{"inspectorTimelineEvents": [1]}')
    self.assertTrue(d.HasTraceFor(trace_data.INSPECTOR_TRACE_PART))
    self.assertEquals(1, len(d.GetTraceFor(trace_data.INSPECTOR_TRACE_PART)))

  def testCorrectlyMalformedStringForm(self):
    d = trace_data.TraceData("""[
      {"ph": "B"}""")
    self.assertTrue(d.HasTraceFor(trace_data.CHROME_TRACE_PART))

  def testCorrectlyMalformedStringForm2(self):
    d = trace_data.TraceData("""[
      {"ph": "B"},""")
    self.assertTrue(d.HasTraceFor(trace_data.CHROME_TRACE_PART))

class TraceDataBuilderTest(unittest.TestCase):
  def testBasicChrome(self):
    builder = trace_data.TraceDataBuilder()
    builder.AddEventsTo(trace_data.CHROME_TRACE_PART, [1, 2, 3])
    builder.AddEventsTo(trace_data.TAB_ID_PART, ['tab-7'])
    builder.SetTraceFor(trace_data.BATTOR_TRACE_PART, 'battor data here')

    d = builder.AsData()
    self.assertTrue(d.HasTraceFor(trace_data.CHROME_TRACE_PART))
    self.assertTrue(d.HasTraceFor(trace_data.TAB_ID_PART))
    self.assertTrue(d.HasTraceFor(trace_data.BATTOR_TRACE_PART))

    self.assertRaises(Exception, builder.AsData)

  def testSetTraceFor(self):
    telemetry_trace = {
        'traceEvents': [1, 2, 3],
        'metadata': {
          'field1': 'value1'
        }
    }

    builder = trace_data.TraceDataBuilder()
    builder.SetTraceFor(trace_data.TELEMETRY_PART, telemetry_trace)
    d = builder.AsData()

    self.assertEqual(d.GetTraceFor(trace_data.TELEMETRY_PART), telemetry_trace)

  def testSetTraceForRaisesWithInvalidPart(self):
    builder = trace_data.TraceDataBuilder()

    self.assertRaises(exceptions.AssertionError,
                      lambda: builder.SetTraceFor('not_a_trace_part', {}))

  def testSetTraceForRaisesWithInvalidTrace(self):
    builder = trace_data.TraceDataBuilder()

    self.assertRaises(exceptions.AssertionError, lambda:
        builder.SetTraceFor(trace_data.TELEMETRY_PART, datetime.time.min))

  def testSetTraceForRaisesWithAlreadySetPart(self):
    builder = trace_data.TraceDataBuilder()
    builder.SetTraceFor(trace_data.TELEMETRY_PART, {})

    self.assertRaises(exceptions.Exception,
        lambda: builder.SetTraceFor(trace_data.TELEMETRY_PART, {}))

  def testSetTraceForRaisesAfterAsData(self):
    builder = trace_data.TraceDataBuilder()
    builder.AsData()

    self.assertRaises(exceptions.Exception,
        lambda: builder.SetTraceFor(trace_data.TELEMETRY_PART, {}))
