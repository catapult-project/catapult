# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from perf_insights.mre import failure as failure_module
from perf_insights.mre import job_results


class JobResultsTests(unittest.TestCase):

  def testJobResultsEmptyByDefault(self):
    results = job_results.JobResults()
    self.assertEquals(results.failures, [])
    self.assertEquals(results.reduce_results, {})

  def testAsDict(self):
    failure = failure_module.Failure('1', '2', '3', 'err', 'desc', 'stack')
    result = {'foo': 'bar'}
    results = job_results.JobResults([failure], result)

    results_dict = results.AsDict()

    self.assertEquals(len(results_dict), 2)
    self.assertEquals(len(results_dict['failures']), 1)
    self.assertEquals(results_dict['reduce_results'], {'foo': 'bar'})

  def testFromDict(self):
    results_dict = {
        'failures': [{
            'job_guid': '1',
            'function_handle_guid': '2',
            'trace_guid': '3',
            'failure_type_name': 'err',
            'description': 'desc',
            'stack': 'stack'
        }],
        'reduce_results': {'foo': 'bar'}
    }

    results = job_results.JobResults.FromDict(results_dict)
    self.assertEquals(len(results.failures), 1)
    self.assertIsInstance(results.failures[0], failure_module.Failure)
    self.assertEquals(results.reduce_results, {'foo': 'bar'})
