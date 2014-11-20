# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.page import page_set
from telemetry.timeline import tracing_timeline_data
from telemetry.unittest_util import system_stub
from telemetry.value import trace

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set = page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

    self._cloud_storage_stub = system_stub.Override(trace, ['cloud_storage'])

  def tearDown(self):
    if self._cloud_storage_stub:
      self._cloud_storage_stub.Restore()
      self._cloud_storage_stub = None

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testAsDict(self):
    v = trace.TraceValue(
        None, tracing_timeline_data.TracingTimelineData({'test' : 1}))
    fh = v.GetAssociatedFileHandle()
    trace.cloud_storage.SetCalculatedHashesForTesting(
        {fh.GetAbsPath(): 123, })
    bucket = trace.cloud_storage.PUBLIC_BUCKET
    cloud_url = v.UploadToCloud(bucket)
    d = v.AsDict()
    self.assertEqual(d['file_id'], fh.id)
    self.assertEqual(d['cloud_url'], cloud_url)
