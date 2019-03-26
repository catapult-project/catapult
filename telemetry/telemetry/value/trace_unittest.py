# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import mock

from py_utils import tempfile_ext
from telemetry import page
from telemetry.value import trace
from tracing.trace_data import trace_data


class ValueTest(unittest.TestCase):
  def testRepr(self):
    with trace.TraceValue(
        page.Page('http://www.bar.com/', name='load:story:bar'),
        trace_data.CreateTestTrace(), important=True, description='desc') as v:
      self.assertEquals("TraceValue('load:story:bar', 'trace')", str(v))

  @mock.patch('telemetry.value.trace.cloud_storage.Insert')
  def testAsDictWhenTraceSerializedAndUploaded(self, insert_mock):
    with tempfile_ext.TemporaryFileName('test.html') as file_path:
      with trace.TraceValue(
          None, trace_data.CreateTestTrace(),
          file_path=file_path,
          upload_bucket=trace.cloud_storage.PUBLIC_BUCKET,
          remote_path='a.html',
          cloud_url='http://example.com/a.html') as v:
        v.SerializeTraceData()
        fh = v.Serialize()
        cloud_url = v.UploadToCloud()
        d = v.AsDict()
        self.assertTrue(os.path.exists(file_path))
        self.assertEqual(d['file_id'], fh.id)
        self.assertEqual(d['cloud_url'], cloud_url)
        insert_mock.assert_called_with(
            trace.cloud_storage.PUBLIC_BUCKET, 'a.html', file_path)

  @mock.patch('telemetry.value.trace.cloud_storage.Insert')
  def testAsDictWhenTraceIsNotSerializedAndUploaded(self, insert_mock):
    with trace.TraceValue(
        None, trace_data.CreateTestTrace(),
        upload_bucket=trace.cloud_storage.PUBLIC_BUCKET,
        remote_path='a.html',
        cloud_url='http://example.com/a.html') as v:
      v.SerializeTraceData()
      cloud_url = v.UploadToCloud()
      d = v.AsDict()
      self.assertEqual(d['cloud_url'], cloud_url)
      insert_mock.assert_called_with(
          trace.cloud_storage.PUBLIC_BUCKET, 'a.html', v.filename)

  def testNoLeakedTempFiles(self):
    with tempfile_ext.NamedTemporaryDirectory() as tempdir:
      with mock.patch('tempfile.tempdir', new=tempdir):
        with trace.TraceValue(None, trace_data.CreateTestTrace()) as v:
          v.SerializeTraceData()

      self.assertTrue(os.path.exists(tempdir))
      self.assertFalse(os.listdir(tempdir))
