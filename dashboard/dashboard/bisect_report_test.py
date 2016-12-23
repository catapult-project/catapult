# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import unittest

from dashboard import bisect_report
from dashboard.common import testing_common
from dashboard.models import try_job


_SAMPLE_BISECT_RESULTS_JSON = json.loads("""
  {
    "issue_url": "https://test-rietveld.appspot.com/200039",
    "aborted_reason": null,
    "bad_revision": "",
    "bisect_bot": "staging_android_nexus5X_perf_bisect",
    "bug_id": 12345,
    "buildbot_log_url": "http://build.chromium.org/513",
    "change": "7.35%",
    "command": "src/tools/perf/run_benchmark foo",
    "culprit_data": null,
    "good_revision": "",
    "metric": "Total/Score",
    "culprit_data": null,
    "revision_data": [],
    "secondary_regressions": [],
    "status": "completed",
    "test_type": "perf",
    "try_job_id": 123456,
    "warnings": []
  }
""")

_SAMPLE_BISECT_REVISION_JSON = json.loads("""
  {
    "build_id": null,
    "commit_hash": "",
    "depot_name": "chromium",
    "failed": false,
    "failure_reason": null,
    "n_observations": 0,
    "result": "unknown",
    "revision_string": ""
  }
""")

_SAMPLE_BISECT_CULPRIT_JSON = json.loads("""
  {
    "author": "author",
    "cl": "cl",
    "cl_date": "Thu Dec 08 01:25:35 2016",
    "commit_info": "commit_info",
    "email": "email",
    "revisions_links": [],
    "subject": "subject"
  }
""")


class BisectReportTest(testing_common.TestCase):

  def setUp(self):
    super(BisectReportTest, self).setUp()

  def _AddTryJob(self, results_data, **kwargs):
    job = try_job.TryJob(results_data=results_data, **kwargs)
    job.put()
    return job

  def _Revisions(self, revisions):
    revision_data = []
    for r in revisions:
      data = copy.deepcopy(_SAMPLE_BISECT_REVISION_JSON)
      data['commit_hash'] = r['commit']
      data['failed'] = r.get('failed', False)
      data['failure_reason'] = r.get('failure_reason', None)
      data['n_observations'] = r.get('num', 0)
      data['revision_string'] = r['commit']
      data['result'] = r.get('result', 'unknown')
      if 'mean' in r:
        data['mean_value'] = r.get('mean', 0)
        data['std_dev'] = r.get('std_dev', 0)
      revision_data.append(data)
    return revision_data

  def _Culprit(self, **kwargs):
    culprit = copy.deepcopy(_SAMPLE_BISECT_CULPRIT_JSON)
    culprit.update(kwargs)
    return culprit

  def _BisectResults(self, **kwargs):
    results = copy.deepcopy(_SAMPLE_BISECT_RESULTS_JSON)
    results.update(kwargs)
    return results

  def testGetReport_CompletedWithCulprit(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 102, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 103, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        culprit_data=self._Culprit(cl=102),
        good_revision=100, bad_revision=103)
    job = self._AddTryJob(results_data)

    log_with_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== SUSPECTED CL(s) =====
Subject : subject
Author  : author
Commit description:
  commit_info
Commit  : 102
Date    : Thu Dec 08 01:25:35 2016


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
101       100   0        10  good
102       200   0        10  bad    <--
103       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""
    self.assertEqual(log_with_culprit, bisect_report.GetReport(job))

  def testGetReport_CompletedWithoutCulprit(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101},
                {'commit': 102},
                {'commit': 103, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        culprit_data=None,
        good_revision=100, bad_revision=103)
    job = self._AddTryJob(results_data)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
103       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

  def testGetReport_CompletedWithBuildFailures(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 102, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 103, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 104, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 105, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        culprit_data=self._Culprit(cl=104),
        good_revision=100, bad_revision=105)
    job = self._AddTryJob(results_data)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== SUSPECTED CL(s) =====
Subject : subject
Author  : author
Commit description:
  commit_info
Commit  : 104
Date    : Thu Dec 08 01:25:35 2016


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
102       100   0        10  good
103       100   0        10  good
104       200   0        10  bad    <--
105       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

  def testGetReport_CompletedCouldntNarrowCulprit(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 102, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 103, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 104, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 105, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 106, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        culprit_data=None,
        good_revision=100, bad_revision=106)
    job = self._AddTryJob(results_data)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N    Good?
100       100   0        10   good
102       100   0        10   good
103       ---   ---      ---  build failure
104       ---   ---      ---  build failure
105       200   0        10   bad
106       200   0        10   bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

  def testGetReport_CompletedMoreThan10BuildFailures(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 102, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 103, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 104, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 105, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 106, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 107, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 108, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 109, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 110, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 111, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 112, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 113, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 114, 'failed': True, 'failure_reason': 'reason'},
                {'commit': 115, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 116, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        culprit_data=None,
        good_revision=100, bad_revision=116)
    job = self._AddTryJob(results_data)

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N    Good?
100       100   0        10   good
102       100   0        10   good
103       ---   ---      ---  build failure
---       ---   ---      ---  too many build failures to list
114       ---   ---      ---  build failure
115       200   0        10   bad
116       200   0        10   bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

  def testGetReport_FailedBisect(self):
    results_data = self._BisectResults(
        good_revision=100, bad_revision=110, status='failed')
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: failed



Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_BisectWithWarnings(self):
    results_data = self._BisectResults(
        status='failed', good_revision=100, bad_revision=103,
        warnings=['A warning.'])
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: failed


=== Warnings ===
The following warnings were raised by the bisect job:

 * A warning.


Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_BisectWithAbortedReason(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 102, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 103, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        good_revision=100, bad_revision=103,
        status='aborted', aborted_reason='Something terrible happened.')
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: aborted


=== Bisection aborted ===
The bisect was aborted because Something terrible happened.
Please contact the the team (see below) if you believe this is in error.

===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
101       100   0        10  good
102       200   0        10  bad
103       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))

  def testGetReport_StatusStarted(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 102, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 103, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        good_revision=100, bad_revision=103,
        status='started')
    job = self._AddTryJob(results_data)

    log_failed_bisect = r"""
===== BISECT JOB RESULTS =====
Status: started


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
101       100   0        10  good
102       200   0        10  bad
103       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 12345

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!"""

    self.assertEqual(log_failed_bisect, bisect_report.GetReport(job))
    # print bisect_report.GetReport(job)

  def testGetReport_WithBugIdBadBisectFeedback(self):
    results_data = self._BisectResults(
        revision_data=self._Revisions(
            [
                {'commit': 100, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 101, 'mean': 100, 'num': 10, 'result': 'good'},
                {'commit': 102, 'mean': 200, 'num': 10, 'result': 'bad'},
                {'commit': 103, 'mean': 200, 'num': 10, 'result': 'bad'},
            ]),
        good_revision=100, bad_revision=103, bug_id=6789)
    job = self._AddTryJob(results_data, bug_id=6789)
    job_id = job.key.id()

    log_without_culprit = r"""
===== BISECT JOB RESULTS =====
Status: completed


===== TESTED REVISIONS =====
Revision  Mean  Std Dev  N   Good?
100       100   0        10  good
101       100   0        10  good
102       200   0        10  bad
103       200   0        10  bad

Bisect job ran on: staging_android_nexus5X_perf_bisect
Bug ID: 6789

Test Command: src/tools/perf/run_benchmark foo
Test Metric: Total/Score
Relative Change: 7.35%%

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200039


Not what you expected? We'll investigate and get back to you!
  https://chromeperf.appspot.com/bad_bisect?try_job_id=%s

| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \ | file a bug with component Tests>AutoBisect.  Thank you!""" % job_id

    self.assertEqual(log_without_culprit, bisect_report.GetReport(job))

if __name__ == '__main__':
  unittest.main()
