# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from perf_insights.mre import failure as failure_module
from perf_insights.mre import mre_result


class MreResultTests(unittest.TestCase):

  def testAsDict(self):
    result = mre_result.MreResult()

    failure = failure_module.Failure('1', '2', '3', 'err', 'desc', 'stack')
    result.AddFailure(failure)

    result.AddPair('foo', 'bar')

    result_dict = result.AsDict()

    self.assertEquals(result_dict['failures'], [failure.AsDict()])
    self.assertEquals(result_dict['pairs'], {'foo': 'bar'})

  def testAddingNonFailure(self):
    result = mre_result.MreResult()
    with self.assertRaises(ValueError):
      result.AddFailure('foo')
