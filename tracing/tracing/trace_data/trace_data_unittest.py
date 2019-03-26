# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import os
import unittest

from py_utils import tempfile_ext
from tracing.trace_data import trace_data


class TraceDataTest(unittest.TestCase):
  def testHasTracesForChrome(self):
    d = trace_data.CreateFromRawChromeEvents([{'ph': 'B'}])
    self.assertTrue(d.HasTracesFor(trace_data.CHROME_TRACE_PART))

  def testHasNotTracesForCpu(self):
    d = trace_data.CreateFromRawChromeEvents([{'ph': 'B'}])
    self.assertFalse(d.HasTracesFor(trace_data.CPU_TRACE_DATA))

  def testGetTracesForChrome(self):
    d = trace_data.CreateFromRawChromeEvents([{'ph': 'B'}])
    ts = d.GetTracesFor(trace_data.CHROME_TRACE_PART)
    self.assertEqual(len(ts), 1)
    self.assertEqual(ts[0], {'traceEvents': [{'ph': 'B'}]})

  def testGetNoTracesForCpu(self):
    d = trace_data.CreateFromRawChromeEvents([{'ph': 'B'}])
    ts = d.GetTracesFor(trace_data.CPU_TRACE_DATA)
    self.assertEqual(ts, [])


class TraceDataBuilderTest(unittest.TestCase):
  def testAddTraceDataAndSerialize(self):
    with tempfile_ext.TemporaryFileName() as trace_path:
      with trace_data.TraceDataBuilder() as builder:
        builder.AddTraceFor(trace_data.CHROME_TRACE_PART,
                            {'traceEvents': [1, 2, 3]})
        builder.Serialize(trace_path)
        self.assertTrue(os.path.exists(trace_path))
        self.assertGreater(os.stat(trace_path).st_size, 0)  # File not empty.

  def testAddTraceForRaisesWithInvalidPart(self):
    with trace_data.TraceDataBuilder() as builder:
      with self.assertRaises(AssertionError):
        builder.AddTraceFor('not_a_trace_part', {})

  def testCantWriteAfterCleanup(self):
    with trace_data.TraceDataBuilder() as builder:
      builder.AddTraceFor(trace_data.CHROME_TRACE_PART,
                          {'traceEvents': [1, 2, 3]})
      builder.CleanUpTraceData()
      with self.assertRaises(Exception):
        builder.AddTraceFor(trace_data.CHROME_TRACE_PART,
                            {'traceEvents': [1, 2, 3]})

  def testCantCallAsDataTwice(self):
    with trace_data.TraceDataBuilder() as builder:
      builder.AddTraceFor(trace_data.CHROME_TRACE_PART,
                          {'traceEvents': [1, 2, 3]})
      builder.AsData().CleanUpAllTraces()
      with self.assertRaises(Exception):
        builder.AsData()


class TraceFileHandleTest(unittest.TestCase):
  def testB64EncodedData(self):
    is_compressed = False
    handle = trace_data.TraceFileHandle(is_compressed)
    handle.Open()
    original_data = {"msg": "The answer is 42"}
    b64_data = base64.b64encode(json.dumps(original_data))
    handle.AppendTraceData(b64_data, b64=True)
    handle.Close()
    out_data = handle.AsTraceData()
    self.assertEqual(original_data, out_data)

  def testB64EncodedCompressedData(self):
    is_compressed = True
    handle = trace_data.TraceFileHandle(is_compressed)
    handle.Open()
    original_data = {"msg": "The answer is 42"}
    # gzip.compress() does not work in python 2. So hardcode the encoded data
    # here.
    b64_compressed_data = "H4sIAIDMblwAA6tWyi1OV7JSUArJSFVIzCs" \
        "uTy1SyCxWMDFSquUCAA4QMtscAAAA"
    handle.AppendTraceData(b64_compressed_data, b64=True)
    handle.Close()
    out_data = handle.AsTraceData()
    self.assertEqual(original_data, out_data)
