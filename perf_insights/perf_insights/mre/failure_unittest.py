# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from perf_insights.mre import failure as failure_module


class FailureTests(unittest.TestCase):

  def testAsDict(self):
    failure = failure_module.Failure('1', '2', '3', 'err', 'desc', 'stack')

    self.assertEquals(failure.AsDict(), {
      'job_guid': '1',
      'function_handle_guid': '2',
      'trace_guid': '3',
      'failure_type_name': 'err',
      'description': 'desc',
      'stack': 'stack'
    })

  def testFromDict(self):
    failure_dict = {
        'job_guid': '1',
        'function_handle_guid': '2',
        'trace_guid': '3',
        'failure_type_name': 'err',
        'description': 'desc',
        'stack': 'stack'
    }

    failure = failure_module.Failure.FromDict(failure_dict)

    self.assertEquals(failure.job_guid, '1')
    self.assertEquals(failure.function_handle_guid, '2')
    self.assertEquals(failure.trace_guid, '3')
    self.assertEquals(failure.failure_type_name, 'err')
    self.assertEquals(failure.description, 'desc')
    self.assertEquals(failure.stack, 'stack')
