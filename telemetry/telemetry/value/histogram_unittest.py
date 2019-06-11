# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import story
from telemetry import page as page_module
from telemetry.value import histogram as histogram_module
from telemetry.value import improvement_direction


class TestBase(unittest.TestCase):
  def setUp(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(
        page_module.Page("http://www.bar.com/", story_set, story_set.base_dir,
                         name='http://www.bar.com/'))
    story_set.AddStory(
        page_module.Page("http://www.baz.com/", story_set, story_set.base_dir,
                         name='http://www.baz.com/'))
    story_set.AddStory(
        page_module.Page("http://www.foo.com/", story_set, story_set.base_dir,
                         name='http://www.foo.com/'))
    self.story_set = story_set

  @property
  def pages(self):
    return self.story_set.stories

class ValueTest(TestBase):
  def testRepr(self):
    page = self.pages[0]
    v = histogram_module.HistogramValue(
        page, 'x', 'counts',
        raw_value_json='{"buckets": [{"low": 1, "high": 2, "count": 1}]}',
        important=True, description='desc', tir_label='my_ir',
        improvement_direction=improvement_direction.UP)
    expected = ('HistogramValue(http://www.bar.com/, x, counts, '
                'raw_json_string={"buckets": [{"low": 1, "high": 2, "count": '
                '1}]}, important=True, description=desc, tir_label=my_ir, '
                'improvement_direction=up, grouping_keys={})')

    self.assertEquals(expected, str(v))

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
        important=False, improvement_direction=improvement_direction.DOWN)
    d = histogram.AsDict()

    self.assertIn('buckets', d.keys())
    self.assertTrue(isinstance(d['buckets'], list))
    self.assertEquals(len(d['buckets']), 1)

  def testMergeLikeValuesFromSamePage(self):
    v0 = histogram_module.HistogramValue(
        None, 'x', 'counts',
        raw_value_json='{"buckets": [{"low": 1, "high": 3, "count": 1}]}',
        description='histogram-based metric')
    v1 = histogram_module.HistogramValue(
        None, 'x', 'counts',
        raw_value_json='{"buckets": [{"low": 2, "high": 4, "count": 1}]}',
        description='histogram-based metric')

    vM = histogram_module.HistogramValue.MergeLikeValuesFromSamePage([v0, v1])
    self.assertTrue(isinstance(vM, histogram_module.HistogramValue))
    self.assertEquals('histogram-based metric', vM.description)
