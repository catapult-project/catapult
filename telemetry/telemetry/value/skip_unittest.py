# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import page as page_module
from telemetry.page import page_set
from telemetry import value
from telemetry.value import skip


class TestBase(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page_module.Page('http://www.bar.com/', ps, ps.base_dir))
    self.page_set = ps

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testBuildbotAndRepresentativeValue(self):
    v = skip.SkipValue(self.pages[0], 'page skipped for testing reason')
    self.assertIsNone(v.GetBuildbotValue())
    self.assertIsNone(v.GetBuildbotDataType(
        value.COMPUTED_PER_PAGE_SUMMARY_OUTPUT_CONTEXT))
    self.assertIsNone(v.GetChartAndTraceNameForPerPageResult())
    self.assertIsNone(v.GetRepresentativeNumber())
    self.assertIsNone(v.GetRepresentativeString())

  def testAsDict(self):
    v = skip.SkipValue(self.pages[0], 'page skipped for testing reason')
    d = v.AsDictWithoutBaseClassEntries()
    self.assertEquals(d['reason'], 'page skipped for testing reason')

  def testFromDict(self):
    d = {
      'type': 'skip',
      'name': 'skip',
      'units': '',
      'reason': 'page skipped for testing reason'
    }
    v = value.Value.FromDict(d, {})
    self.assertTrue(isinstance(v, skip.SkipValue))
    self.assertEquals(v.reason, 'page skipped for testing reason')
