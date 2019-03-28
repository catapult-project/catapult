#!/usr/bin/env python
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import StringIO

from py_trace_event.trace_event_impl import perfetto_trace_writer


class PerfettoTraceWriterTest(unittest.TestCase):
  """ Tests functions that write perfetto protobufs.

  TODO(crbug.com/944078): Switch to using python-protobuf library
  and implement proper protobuf parsing then.
  """


  def testWriteThreadDescriptorEvent(self):
    result = StringIO.StringIO()
    perfetto_trace_writer.write_thread_descriptor_event(
        output=result,
        pid=1,
        tid=2,
        ts=2076949764620672,
    )
    expected_output = (
        '\n\x18P\x80\x80@\xc8\x02\x01\xe2\x02\x0e\x08\x01\x10'
        '\x020\x80\xb8\xaf\xc4\xe8\xd9\xb3\xe9\x1c'
    )
    self.assertEqual(expected_output, result.getvalue())

  def testWriteTwoEvents(self):
    result = StringIO.StringIO()
    perfetto_trace_writer.write_thread_descriptor_event(
        output=result,
        pid=1,
        tid=2,
        ts=2076949764620672,
    )
    perfetto_trace_writer.write_event(
        output=result,
        ph="M",
        category="category",
        name="event_name",
        ts=2076949764620673,
        args={},
        tid=2,
    )
    expected_output = (
       '\n\x18P\x80\x80@\xc8\x02\x01\xe2\x02\x0e\x08\x01\x10\x020\x80\xb8'
       '\xaf\xc4\xe8\xd9\xb3\xe9\x1c\n1P\x80\x80@Z\x0b\x08\xe8\x07\x18\x002'
       '\x04\x08\x00\x10Mb\x1e\n\x0c\x08\x00\x12\x08category'
       '\x12\x0e\x08\x00\x12\nevent_name'
    )
    self.assertEqual(expected_output, result.getvalue())

