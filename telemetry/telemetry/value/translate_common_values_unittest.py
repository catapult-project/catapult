# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import os

from perf_insights import function_handle
from perf_insights.mre import failure
from perf_insights.mre import job as job_module

from telemetry import page
from telemetry import story
from telemetry.value import translate_common_values


def _SingleFileFunctionHandle(filename, function_name, guid):
  return function_handle.FunctionHandle(
      modules_to_load=[function_handle.ModuleToLoad(filename=filename)],
      function_name=function_name, guid=guid)


class TranslateCommonValuesTest(unittest.TestCase):
  def testTranslateMreFailure(self):
    map_function_handle = _SingleFileFunctionHandle('foo.html', 'Foo', '2')
    reduce_function_handle = _SingleFileFunctionHandle('bar.html', 'Bar', '3')
    job = job_module.Job(map_function_handle, reduce_function_handle, '1')

    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    p = page.Page('http://www.foo.com/', story_set, story_set.base_dir)

    f = failure.Failure(job, 'foo', '/a.json', 'MyFailure', 'failure', 'stack')
    fv = translate_common_values.TranslateMreFailure(f, p)

    self.assertIn('stack', str(fv))
