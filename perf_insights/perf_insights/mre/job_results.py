# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from perf_insights.mre import failure as failure_module


class JobResults(object):

  def __init__(self, failures=None, reduce_results=None):
    if failures is None:
      failures = []
    if reduce_results is None:
      reduce_results = {}
    self._failures = failures
    self._reduce_results = reduce_results

  @property
  def failures(self):
      return self._failures

  @property
  def reduce_results(self):
      return self._reduce_results

  def AsDict(self):
    return {
        'failures': [failure.AsDict() for failure in self._failures],
        'reduce_results': self.reduce_results
    }

  @staticmethod
  def FromDict(job_results_dict):
    failures = map(failure_module.Failure.FromDict,
                   job_results_dict['failures'])
    reduce_results = job_results_dict['reduce_results']

    return JobResults(failures, reduce_results)
