# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set
from telemetry.value import histogram as histogram_module

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set =  page_set.PageSet.FromDict({
      "description": "hello",
      "archive_path": "foo.wpr",
      "pages": [
        {"url": "http://www.bar.com/"},
        {"url": "http://www.baz.com/"},
        {"url": "http://www.foo.com/"}
        ]
      }, os.path.dirname(__file__))

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testHistogramBasic(self):
    page0 = self.pages[0]
    histogram = histogram_module.HistogramValue(
        page0, 'x', 'counts',
        raw_value_json='{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
        important=False)
    self.assertEquals(
      ['{"buckets": [{"low": 1, "high": 2, "count": 1}]}'],
      histogram.GetBuildbotValue())
    self.assertEquals(1.5,
                      histogram.GetRepresentativeNumber())
    self.assertEquals(
      ['{"buckets": [{"low": 1, "high": 2, "count": 1}]}'],
      histogram.GetBuildbotValue())

    self.assertEquals(
        'unimportant-histogram',
        histogram.GetBuildbotDataType(value.SUMMARY_RESULT_OUTPUT_CONTEXT))
    histogram.important = True
    self.assertEquals(
        'histogram',
        histogram.GetBuildbotDataType(value.SUMMARY_RESULT_OUTPUT_CONTEXT))
