# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import unittest

from dashboard import bisect_report
from dashboard import testing_common
from dashboard.models import try_job

_SAMPLE_BISECT_RESULTS_JSON = {
    'try_job_id': None,
    'bug_id': None,
    'status': None,
    'bisect_bot': 'linux',
    'buildbot_log_url': 'http://build.chromium.org/513',
    'command': ('tools/perf/run_benchmark -v '
                '--browser=release page_cycler'),
    'metric': 'page_load_time',
    'test_type': 'perf',
    'issue_url': 'https://test-rietveld.appspot.com/200039',
    'change': 10,
    'score': 99.9,
    'good_revision': '306475',
    'bad_revision': '306477',
    'warnings': None,
    'aborted_reason': None,
    'culprit_data': {
        'subject': 'subject',
        'author': 'author',
        'email': 'author@email.com',
        'cl_date': '1/2/2015',
        'commit_info': 'commit info',
        'revisions_links': ['http://src.chromium.org/viewvc/chrome?view='
                            'revision&revision=306476'],
        'cl': '306476abcdabcdfabcdfabcdfabcdfabcdfabcdf'
    },
    'revision_data': [
        {
            'depot_name': 'chromium',
            'commit_hash': '306475abcdabcdfabcdfabcdfabcdfabcdfabcdf',
            'revision_string': 'chromium@306475',
            'mean_value': 70,
            'std_dev': 0,
            'values': [70, 70, 70],
            'result': 'good'
        },
        {
            'revision_string': 'chromium@306476',
            'commit_hash': '306476abcdabcdfabcdfabcdfabcdfabcdfabcdf',
            'depot_name': 'chromium',
            'mean_value': 80,
            'std_dev': 0,
            'values': [80, 80, 80],
            'result': 'bad'
        },
        {
            'revision_string': 'chromium@306477',
            'depot_name': 'chromium',
            'commit_hash': '306477abcdabcdfabcdfabcdfabcdfabcdfabcdf',
            'mean_value': 80,
            'std_dev': 0,
            'values': [80, 80, 80],
            'result': 'bad'
        }
    ]
}


class BisectReportTest(testing_common.TestCase):

  def setUp(self):
    super(BisectReportTest, self).setUp()

  def _AddTryJob(self, results_data, **kwargs):
    job = try_job.TryJob(results_data=results_data, **kwargs)
    job.put()
    return job

  def _BisectResults(self, try_job_id, bug_id, status, **kwargs):
    results = copy.deepcopy(_SAMPLE_BISECT_RESULTS_JSON)
    results['try_job_id'] = try_job_id
    results['bug_id'] = bug_id
    results['status'] = status
    results.update(kwargs)
    return results

  def testGetReport_CompletedWithCulprit(self):
    results_data = self._BisectResults(6789, 12345, 'completed')
    job = self._AddTryJob(results_data)

    log_with_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== SUSPECTED CL(s) =====
Subject : subject
Author  : author
Commit description:
  commit info
Commit  : 306476abcdabcdfabcdfabcdfabcdfabcdfabcdf
Date    : 1/2/2015


===== TESTED REVISIONS =====
Revision                Mean Value  Std. Dev.   Num Values  Good?
chromium@306475         70          0           3           good
chromium@306476         80          0           3           bad         <-
chromium@306477         80          0           3           bad

Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 99.9

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""
    self.assertEqual(log_with_culprit, bisect_report.GetReport(job))

  def testGetReport_CompletedWithoutCulprit(self):
    results_data = self._BisectResults(6789, 12345, 'completed',
                                       culprit_data=None, score=0)
    job = self._AddTryJob(results_data)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision                Mean Value  Std. Dev.   Num Values  Good?
chromium@306475         70          0           3           good
chromium@306476         80          0           3           bad
chromium@306477         80          0           3           bad

Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 0

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

  def testGetReport_FailedBisect(self):
    results_data = self._BisectResults(6789, 12345, 'failed',
                                       culprit_data=None, score=0,
                                       revision_data=None)
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: failed



Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 0

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_BisectWithWarnings(self):
    results_data = self._BisectResults(6789, 12345, 'failed',
                                       culprit_data=None, score=0,
                                       revision_data=None,
                                       warnings=['A warning.'])
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: failed


=== Warnings ===
The following warnings were raised by the bisect job:

 * A warning.


Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 0

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_BisectWithAbortedReason(self):
    results_data = self._BisectResults(6789, 12345, 'aborted',
                                       culprit_data=None, score=0,
                                       revision_data=None,
                                       aborted_reason='invalid revisions.')
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: aborted


=== Bisection aborted ===
The bisect was aborted because invalid revisions.
Please contact the the team (see below) if you believe this is in error.


Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 0

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_WithBugIdBadBisectFeedback(self):
    results_data = self._BisectResults(6789, 12345, 'completed',
                                       culprit_data=None, score=0)
    job = self._AddTryJob(results_data, bug_id=6789)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision                Mean Value  Std. Dev.   Num Values  Good?
chromium@306475         70          0           3           good
chromium@306476         80          0           3           bad
chromium@306477         80          0           3           bad

Bisect job ran on: linux
Bug ID: 12345

Test Command: tools/perf/run_benchmark -v --browser=release page_cycler
Test Metric: page_load_time
Relative Change: 10
Score: 0

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


Not what you expected? We'll investigate and get back to you!
  https://chromeperf.appspot.com/bad_bisect?try_job_id=6789

| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""
    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

if __name__ == '__main__':
  unittest.main()
