# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import page as page_module
from telemetry.page import page_set
from telemetry import value
from telemetry.value import histogram as histogram_module


class TestBase(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page_module.Page("http://www.bar.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.baz.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.foo.com/", ps, ps.base_dir))
    self.page_set = ps

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

  def testBucketAsDict(self):
    bucket = histogram_module.HistogramValueBucket(33, 45, 78)
    d = bucket.AsDict()

    self.assertEquals(d, {
          'low': 33,
          'high': 45,
          'count': 78
        })

  def testAsDict(self):
    histogram = histogram_module.HistogramValue(
        None, 'x', 'counts',
        raw_value_json='{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
        important=False)
    d = histogram.AsDictWithoutBaseClassEntries()

    self.assertEquals(['buckets'], d.keys())
    self.assertTrue(isinstance(d['buckets'], list))
    self.assertEquals(len(d['buckets']), 1)

  def testFromDict(self):
    d = {
      'type': 'histogram',
      'name': 'x',
      'units': 'counts',
      'buckets': [{'low': 1, 'high': 2, 'count': 1}]
    }
    v = value.Value.FromDict(d, {})

    self.assertTrue(isinstance(v, histogram_module.HistogramValue))
    self.assertEquals(
      ['{"buckets": [{"low": 1, "high": 2, "count": 1}]}'],
      v.GetBuildbotValue())
