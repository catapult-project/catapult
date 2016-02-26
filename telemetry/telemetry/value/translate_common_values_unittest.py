# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import os

from perf_insights.mre import failure

from telemetry import page
from telemetry import story
from telemetry.value import translate_common_values

class TranslateCommonValuesTest(unittest.TestCase):
  def testTranslateMreFailure(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    p = page.Page('http://www.foo.com/', story_set, story_set.base_dir)

    f = failure.Failure(None, 'foo', '/a.json', 'MyFailure', 'failure', 'stack')
    fv = translate_common_values.TranslateMreFailure(f, p)

    self.assertIn('stack', str(fv))
