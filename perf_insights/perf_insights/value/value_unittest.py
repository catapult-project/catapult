# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from perf_insights import value as value_module
from perf_insights.value import run_info as run_info_module

class ValueTests(unittest.TestCase):
  def testDict(self):
    run_info = run_info_module.RunInfo('file:///a.json', '/a.json',
                                       metadata={'m': 1})
    d = {
      'run_id': run_info.run_id,
      'type': 'dict',
      'name': 'MyDictValue',
      'important': False,
      'value': {'a': 1, 'b': 'b'}
    }
    v = value_module.Value.FromDict(run_info, d)
    self.assertTrue(isinstance(v, value_module.DictValue))
    d2 = v.AsDict()

    self.assertEquals(d, d2)


  def testFailure(self):
    run_info = run_info_module.RunInfo('file:///a.json', '/a.json',
                                       metadata={'m': 1})

    d = {
      'run_id': run_info.run_id,
      'type': 'failure',
      'name': 'Error',
      'important': False,
      'description': 'Some error message',
      'stack_str': 'Some stack string'
    }
    v = value_module.Value.FromDict(run_info, d)
    self.assertTrue(isinstance(v, value_module.FailureValue))
    d2 = v.AsDict()

    self.assertEquals(d, d2)