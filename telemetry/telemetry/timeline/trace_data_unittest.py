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
    ri = trace_data.CreateTraceDataFromRawData({'traceEvents': [1, 2, 3]})
    f = cStringIO.StringIO()
    ri.Serialize(f)
    d = f.getvalue()

    self.assertIn('traceEvents', d)
    self.assertIn('[1, 2, 3]', d)

    json.loads(d)

  def testSerializeZip(self):
    data = trace_data.CreateTraceDataFromRawData({'traceEvents': [1, 2, 3],
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

  def testEmptyArrayValue(self):
    # We can import empty lists and empty string.
    d = trace_data.CreateTraceDataFromRawData([])
    self.assertFalse(d.HasTracesFor(trace_data.CHROME_TRACE_PART))

  def testInvalidTrace(self):
    with self.assertRaises(AssertionError):
      trace_data.CreateTraceDataFromRawData({'hello': 1})

  def testListForm(self):
    d = trace_data.CreateTraceDataFromRawData([{'ph': 'B'}])
    self.assertTrue(d.HasTracesFor(trace_data.CHROME_TRACE_PART))
    events = d.GetTracesFor(trace_data.CHROME_TRACE_PART)[0].get(
        'traceEvents', [])
    self.assertEquals(1, len(events))

  def testStringForm(self):
    d = trace_data.CreateTraceDataFromRawData('[{"ph": "B"}]')
    self.assertTrue(d.HasTracesFor(trace_data.CHROME_TRACE_PART))
    events = d.GetTracesFor(trace_data.CHROME_TRACE_PART)[0].get(
        'traceEvents', [])
    self.assertEquals(1, len(events))


class TraceDataBuilderTest(unittest.TestCase):
  def testBasicChrome(self):
    builder = trace_data.TraceDataBuilder()
    builder.AddTraceFor(trace_data.CHROME_TRACE_PART,
                        {'traceEvents': [1, 2, 3]})
    builder.AddTraceFor(trace_data.TAB_ID_PART, ['tab-7'])
    builder.AddTraceFor(trace_data.BATTOR_TRACE_PART, 'battor data here')

    d = builder.AsData()
    self.assertTrue(d.HasTracesFor(trace_data.CHROME_TRACE_PART))
    self.assertTrue(d.HasTracesFor(trace_data.TAB_ID_PART))
    self.assertTrue(d.HasTracesFor(trace_data.BATTOR_TRACE_PART))

    self.assertRaises(Exception, builder.AsData)

  def testSetTraceFor(self):
    telemetry_trace = {
        'traceEvents': [1, 2, 3],
        'metadata': {
          'field1': 'value1'
        }
    }

    builder = trace_data.TraceDataBuilder()
    builder.AddTraceFor(trace_data.TELEMETRY_PART, telemetry_trace)
    d = builder.AsData()

    self.assertEqual(d.GetTracesFor(trace_data.TELEMETRY_PART),
                     [telemetry_trace])

  def testSetTraceForRaisesWithInvalidPart(self):
    builder = trace_data.TraceDataBuilder()

    self.assertRaises(exceptions.AssertionError,
                      lambda: builder.AddTraceFor('not_a_trace_part', {}))

  def testSetTraceForRaisesWithInvalidTrace(self):
    builder = trace_data.TraceDataBuilder()

    self.assertRaises(exceptions.AssertionError, lambda:
        builder.AddTraceFor(trace_data.TELEMETRY_PART, datetime.time.min))

  def testSetTraceForRaisesAfterAsData(self):
    builder = trace_data.TraceDataBuilder()
    builder.AsData()

    self.assertRaises(exceptions.Exception,
        lambda: builder.AddTraceFor(trace_data.TELEMETRY_PART, {}))
