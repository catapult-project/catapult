# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
import webapp2
import webtest

from dashboard import layered_cache
from dashboard import rietveld_service
from dashboard import testing_common
from dashboard import update_bug_with_results
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models import try_job

# Bisect log with multiple potential culprits with different authors.
_BISECT_LOG_MULTI_OWNER = """
@@@STEP_CURSOR Results@@@
@@@STEP_STARTED@@@

===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total
Relative Change: 1.23% (+/-1.26%)
Estimated Confidence: 99.9%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  : sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Date    : Sat, 22 Jun 2013 00:59:35 +0000

Subject : Subject 2
Author  : prasadv@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Date    : Sat, 22 Jun 2013 00:57:48 +0000

Subject : Subject 3
Author  :   qyearsley@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Date    : Sat, 22 Jun 2013 00:55:52 +0000
"""

# Bisect log with multiple potential culprits but same Author.
_BISECT_LOG_MULTI_SAME_OWNER = """
@@@STEP_CURSOR Results@@@
@@@STEP_STARTED@@@

===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total
Relative Change: 1.23% (+/-1.26%)
Estimated Confidence: 99.9%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  :   sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Date    : Sat, 22 Jun 2013 00:59:35 +0000

Subject : Subject 2
Author  : sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Date    : Sat, 22 Jun 2013 00:57:48 +0000:55:52 +0000
"""

# Bisect log with single potential culprits.
_BISECT_LOG_SINGLE_OWNER = """
@@@STEP_CURSOR Results@@@
@@@STEP_STARTED@@@

===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total
Relative Change: 1.23% (+/-1.26%)
Estimated Confidence: 100%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  :   sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Commit  : d6432657771a9fd720179d8c3dd64c8daee025c7
Date    : Sat, 22 Jun 2013 00:59:35 +0000
"""

_EXPECTED_BISECT_LOG_SINGLE_OWNER = """

===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total
Relative Change: 1.23% (+/-1.26%)
Estimated Confidence: 100%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  :   sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Commit  : d6432657771a9fd720179d8c3dd64c8daee025c7
Date    : Sat, 22 Jun 2013 00:59:35 +0000"""

_EXPECTED_BISECT_RESULTS_ON_BUG = """
==== Auto-CCing suspected CL author sullivan@google.com ====

Hi sullivan@google.com, the bisect results pointed to your CL below as possibly
causing a regression. Please have a look at this info and see whether
your CL be related.

Bisect job status: Completed
Bisect job ran on: win_perf_bisect



===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total\nRelative Change: 1.23% (+/-1.26%)
Estimated Confidence: 100%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  :   sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20798
Commit  : d6432657771a9fd720179d8c3dd64c8daee025c7
Date    : Sat, 22 Jun 2013 00:59:35 +0000

Buildbot stdio: http://build.chromium.org/513
Job details: https://test-rietveld.appspot.com/200037
"""

_BISECT_LOG_FAILED_REVISION = """
@@@STEP_CURSOR Results@@@
@@@STEP_STARTED@@@

===== BISECT JOB RESULTS =====
Status: Positive

Test Command: python tools/perf/run_benchmark -v --browser=release sunspider
Test Metric: Total/Total
Relative Change: 1.23% (+/-1.26%)
Estimated Confidence: 99.9%

===== SUSPECTED CL(s) =====
Subject : Subject 1
Author  :   sullivan@google.com
Link    : http://src.chromium.org/viewvc/chrome?view=revision&revision=20799
Commit  : a80773bb263a9706cc8ee4e3f336d2d3d28fadd8
Date    : Sat, 22 Jun 2013 00:59:35 +0000
"""

_BISECT_LOG_PARTIAL_RESULT = """
===== PARTIAL RESULTS =====
Depot Commit SHA Mean Std. Error State
chromium 282472 91730.00 +-0.00 Bad

chromium 282469 92973.00 +-0.00 Good
chromium 282460 93468.00 +-0.00 Good


"""

_EXPECTED_BISECT_LOG_PARTIAL_RESULT = u"""Bisect job status: Failure with \
partial results
Bisect job ran on: win_perf_bisect

Completed 1/2 builds.
Run time: 724/720 minutes.
Bisect timed out! Try again with a smaller revision range.
Failed steps: slave_steps, Working on def

===== PARTIAL RESULTS =====
Depot Commit SHA Mean Std. Error State
chromium 282472 91730.00 +-0.00 Bad

chromium 282469 92973.00 +-0.00 Good
chromium 282460 93468.00 +-0.00 Good

Buildbot stdio: http://build.chromium.org/builders/515
Job details: https://test-rietveld.appspot.com/200039
"""

_REVISION_RESPONSE = """
<html xmlns=....>
<head><title>[chrome] Revision 207985</title></head><body><table>....
<tr align="left">
<th>Log Message:</th>
<td> Message....</td>
&gt; &gt; Review URL: <a href="https://codereview.chromium.org/81533002">\
https://codereview.chromium.org/81533002</a>
&gt;
&gt; Review URL: <a href="https://codereview.chromium.org/96073002">\
https://codereview.chromium.org/96073002</a>

Review URL: <a href="https://codereview.chromium.org/17504006">\
https://codereview.chromium.org/96363002</a></pre></td></tr></table>....</body>
</html>
"""

_PERF_TEST_CONFIG = """config = {
  'command': 'tools/perf/run_benchmark -v --browser=release\
dromaeo.jslibstylejquery --profiler=trace',
  'good_revision': '215806',
  'bad_revision': '215828',
  'repeat_count': '1',
  'max_time_minutes': '120',
  'truncate_percent': '0'
}"""

_PERF_LOG_EXPECTED_TITLE_1 = 'With Patch - Profiler Data[0]'
_PERF_LOG_EXPECTED_TITLE_2 = 'Without Patch - Profiler Data[0]'
_PERF_LOG_EXPECTED_PROFILER_LINK1 = (
    'https://console.developers.google.com/m/cloudstorage/b/chrome-telemetry/o/'
    'profiler-file-id_0-2014-11-27_14-08-5560487.json')
_PERF_LOG_EXPECTED_PROFILER_LINK2 = (
    'https://console.developers.google.com/m/cloudstorage/b/chrome-telemetry/o/'
    'profiler-file-id_0-2014-11-27_14-10-1644780.json')
_PERF_LOG_EXPECTED_HTML_LINK = (
    'http://storage.googleapis.com/chromium-telemetry/html-results/'
    'results-2014-11-27_14-10-21')
_PERF_LOG_WITH_RESULTS = """
@@@STEP_CLOSED@@@


@@@STEP_LINK@HTML Results@%s@@@


@@@STEP_LINK@%s@%s@@@


@@@STEP_LINK@%s@%s@@@
""" % (_PERF_LOG_EXPECTED_HTML_LINK, _PERF_LOG_EXPECTED_TITLE_1,
       _PERF_LOG_EXPECTED_PROFILER_LINK1, _PERF_LOG_EXPECTED_TITLE_2,
       _PERF_LOG_EXPECTED_PROFILER_LINK2)

_ISSUE_RESPONSE = """
    {
      "description": "Issue Description.",
      "cc": [
              "chromium-reviews@chromium.org",
              "cc-bugs@chromium.org",
              "sullivan@google.com"
            ],
      "reviewers": [
                      "prasadv@google.com"
                   ],
      "owner_email": "sullivan@google.com",
      "private": false,
      "base_url": "svn://chrome-svn/chrome/trunk/src/",
      "owner":"sullivan",
      "subject":"Issue Subject",
      "created":"2013-06-20 22:23:27.227150",
      "patchsets":[1,21001,29001],
      "modified":"2013-06-22 00:59:38.530190",
      "closed":true,
      "commit":false,
      "issue":17504006
    }
"""

_BISECT_LOG_INFRA_FAILURE = 'Failed to produce build'

# Globals that are set in mock functions and then checked in tests.
_TEST_RECEIEVED_EMAIL_RESULTS = None
_TEST_RECEIVED_EMAIL = None


def _MockGetJobStatus(job):
  id_to_response_map = {
      # Complete
      '1234567': {
          'result': 'SUCCESS',
          'result_details': {
              'buildername': 'Fake_Bot',
          },
          'url': 'http://build.chromium.org/bb1234567',
          'status': 'COMPLETED',
      },
      # In progress
      '11111': {
          'result_details': {
              'buildername': 'Fake_Bot',
          },
          'url': 'http://build.chromium.org/bb11111',
          'status': 'STARTED',
      },
      # Failed
      '66666': {
          'result': 'FAILURE',
          'result_details': {
              'buildername': 'Fake_Bot',
          },
          'url': 'http://build.chromium.org/bb66666',
          'status': 'COMPLETED',
      },
  }
  return id_to_response_map.get(str(job.buildbucket_job_id))


def _MockFetch(url=None):
  url_to_response_map = {
      'https://test-rietveld.appspot.com/api/200034/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/508'}]})
      ],
      'https://test-rietveld.appspot.com/api/302304/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '2',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/509'}]})
      ],
      'https://test-rietveld.appspot.com/api/100001/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '6',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/510'}]})
      ],
      'https://test-rietveld.appspot.com/api/200035/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/511'}]})
      ],
      'https://test-rietveld.appspot.com/api/200036/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/512'}]})
      ],
      'https://test-rietveld.appspot.com/api/200037/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/513'}]})
      ],
      'https://test-rietveld.appspot.com/api/200038/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/514'}]})
      ],
      'https://test-rietveld.appspot.com/api/200039/1': [
          200,
          json.dumps({'try_job_results': [{
              'result': '0',
              'builder': 'win_perf_bisect',
              'url': 'http://build.chromium.org/builders/515'}]})
      ],
      'http://build.chromium.org/json/builders/515': [
          200,
          json.dumps({
              'steps': [{'name': 'Working on abc', 'results': [0]},
                        {'name': 'Working on def', 'results': [2]}],
              'times': [1411501756.293642, 1411545237.89049],
              'text': ['failed', 'slave_steps', 'failed', 'Working on def']})
      ],
      'http://build.chromium.org/bb1234567/steps/Results/logs/stdio/text': [
          200, _BISECT_LOG_SINGLE_OWNER
      ],
      'http://build.chromium.org/bb66666': [
          200,
          json.dumps({
              'steps': [{'name': 'Working on abc', 'results': [0]},
                        {'name': 'Working on def', 'results': [2]}],
              'times': [1411501756.293642, 1411545237.89049],
              'text': ['failed', 'slave_steps', 'failed', 'Working on def']})
      ],
      ('http://build.chromium.org/builders/bb66666'
       '/steps/Results/logs/stdio/text'): [
           404, ''
       ],
      'http://build.chromium.org/json/builders/516': [
          200,
          json.dumps({'steps': [{'name': 'gclient', 'results': [2]}]})
      ],
      'http://src.chromium.org/viewvc/chrome?view=revision&revision=20798': [
          200, _REVISION_RESPONSE
      ],
      'http://src.chromium.org/viewvc/chrome?view=revision&revision=20799': [
          200, 'REVISION REQUEST FAILED!'
      ],
      'https://codereview.chromium.org/api/17504006': [
          200, json.dumps(json.loads(_ISSUE_RESPONSE))
      ],
      'http://build.chromium.org/508/steps/Results/logs/stdio/text': [
          200, '===== BISECT JOB RESULTS ====='
      ],
      'http://build.chromium.org/509/steps/Results/logs/stdio/text': [
          200, 'BISECT FAILURE! '
      ],
      'http://build.chromium.org/511/steps/Results/logs/stdio/text': [
          200, _BISECT_LOG_MULTI_OWNER
      ],
      'http://build.chromium.org/512/steps/Results/logs/stdio/text': [
          200, _BISECT_LOG_MULTI_SAME_OWNER
      ],
      'http://build.chromium.org/513/steps/Results/logs/stdio/text': [
          200, _BISECT_LOG_SINGLE_OWNER
      ],
      'http://build.chromium.org/514/steps/Results/logs/stdio/text': [
          200, _BISECT_LOG_FAILED_REVISION
      ],
      'http://build.chromium.org/builders/515/steps/Results/logs/stdio/text': [
          404, ''
      ],
      'http://build.chromium.org/builders/515/steps/Working%20on%20abc/logs/'
      'stdio/text': [
          200, _BISECT_LOG_PARTIAL_RESULT
      ],
      'http://build.chromium.org/builders/516/steps/slave_steps/logs/stdio/'
      'text': [
          200, _BISECT_LOG_INFRA_FAILURE
      ],
      'http://build.chromium.org/508/steps/Running%20Bisection/logs/stdio/'
      'text': [
          200, _PERF_LOG_WITH_RESULTS
      ],
      'http://build.chromium.org/511/steps/Running%20Bisection/logs/stdio/'
      'text': [
          200, ''
      ],
  }

  if url not in url_to_response_map:
    assert False, 'Bad url %s' % url

  response_code = url_to_response_map[url][0]
  response = url_to_response_map[url][1]
  return testing_common.FakeResponseObject(response_code, response)


def _MockSendPerfTryJobEmail(_, results):
  global _TEST_RECEIEVED_EMAIL_RESULTS
  _TEST_RECEIEVED_EMAIL_RESULTS = results


def _MockSendMail(**kwargs):
  global _TEST_RECEIVED_EMAIL
  _TEST_RECEIVED_EMAIL = kwargs


class UpdateBugWithResultsTest(testing_common.TestCase):

  def setUp(self):
    super(UpdateBugWithResultsTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/update_bug_with_results',
        update_bug_with_results.UpdateBugWithResultsHandler)])
    self.testapp = webtest.TestApp(app)
    self._AddRietveldConfig()
    # Calling the real Credentials function doesn't work in the test
    # environment; using no credentials in the tests works because the requests
    # to the issue tracker are mocked out as well.
    rietveld_service.Credentials = mock.MagicMock(return_value=None)

  def _AddRietveldConfig(self):
    """Adds a RietveldConfig entity to the datastore.

    This is used in order to get the Rietveld URL when requests are made to the
    handler in te tests below. In the real datastore, the RietveldConfig entity
    would contain credentials.
    """
    rietveld_service.RietveldConfig(
        id='default_rietveld_config',
        client_email='sullivan@google.com',
        service_account_key='Fake Account Key',
        server_url='https://test-rietveld.appspot.com',
        internal_server_url='https://test-rietveld.appspot.com').put()

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  @mock.patch.object(
      update_bug_with_results.buildbucket_service, 'GetJobStatus',
      _MockGetJobStatus)
  def testGet(self):
    # Put succeeded, failed, and not yet finished jobs in the datastore.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    try_job.TryJob(
        bug_id=54321, rietveld_issue_id=302304, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    try_job.TryJob(
        bug_id=99999, rietveld_issue_id=100001, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    try_job.TryJob(
        bug_id=77777, buildbucket_job_id='1234567', use_buildbucket=True,
        status='started', bot='win_perf').put()
    # Create bug.
    bug_data.Bug(id=12345).put()
    bug_data.Bug(id=54321).put()
    bug_data.Bug(id=99999).put()
    bug_data.Bug(id=77777).put()

    self.testapp.get('/update_bug_with_results')
    pending_jobs = try_job.TryJob.query().fetch()
    # Expects a failed and not yet finished bisect job to be in datastore.
    self.assertEqual(3, len(pending_jobs))
    self.assertEqual(54321, pending_jobs[0].bug_id)
    self.assertEqual('failed', pending_jobs[0].status)
    self.assertEqual(99999, pending_jobs[1].bug_id)
    self.assertEqual(77777, pending_jobs[2].bug_id)
    self.assertEqual('started', pending_jobs[1].status)
    self.assertEqual('started', pending_jobs[2].status)
    self.assertEqual('bisect', pending_jobs[0].job_type)
    self.assertEqual('bisect', pending_jobs[1].job_type)
    self.assertEqual('bisect', pending_jobs[2].job_type)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  def testCreateTryJob_WithoutExistingBug(self):
    # Put succeeded job in the datastore.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()

    self.testapp.get('/update_bug_with_results')
    pending_jobs = try_job.TryJob.query().fetch()

    # Expects job to finish.
    self.assertEqual(0, len(pending_jobs))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment', mock.MagicMock(return_value=False))
  @mock.patch('logging.error')
  def testGet_FailsToUpdateBug_LogsErrorAndMovesOn(self, mock_logging_error):
    # Put a successful job and a failed job with partial results.
    # Note that AddBugComment is mocked to always returns false, which
    # simulates failing to post results to the issue tracker for all bugs.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    try_job.TryJob(
        bug_id=54321, rietveld_issue_id=200039, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    bug_data.Bug(id=12345).put()
    bug_data.Bug(id=54321).put()

    self.testapp.get('/update_bug_with_results')

    # Two errors should be logged.
    self.assertEqual(2, mock_logging_error.call_count)
    mock_logging_error.assert_called_with(
        'Caught Exception %s: %s', 'BugUpdateFailure', mock.ANY)

    # The pending jobs should still be there.
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(2, len(pending_jobs))
    self.assertEqual('started', pending_jobs[0].status)
    self.assertEqual('started', pending_jobs[1].status)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_BisectJobWithPartialResults(self, mock_update_bug):
    # Put failed job in the datastore.
    try_job.TryJob(
        bug_id=54321, rietveld_issue_id=200039, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    # Create bug.
    bug_data.Bug(id=54321).put()

    self.testapp.get('/update_bug_with_results')

    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(1, len(pending_jobs))
    self.assertEqual('failed', pending_jobs[0].status)
    mock_update_bug.assert_called_once_with(
        54321, _EXPECTED_BISECT_LOG_PARTIAL_RESULT, labels=None)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_BisectCulpritHasMultipleAuthors_NoneCCd(self, mock_update_bug):
    # When a bisect finds multiple culprits for a perf regression,
    # owners of CLs shouldn't be cc'ed on issue update.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200035, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    bug_data.Bug(id=12345).put()

    self.testapp.get('/update_bug_with_results')

    mock_update_bug.assert_called_once_with(
        mock.ANY, mock.ANY, cc_list=[], merge_issue=None, labels=None,
        owner=None)
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(0, len(pending_jobs))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_MultipleCulpritsSameAuthor_AssignsAuthor(self, mock_update_bug):
    # When a bisect finds multiple culprits by same Author for a perf
    # regression, owner of CLs should be cc'ed.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200036, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    bug_data.Bug(id=12345).put()

    self.testapp.get('/update_bug_with_results')

    mock_update_bug.assert_called_once_with(
        mock.ANY, mock.ANY,
        cc_list=['sullivan@google.com', 'prasadv@google.com'],
        merge_issue=None, labels=None, owner='sullivan@google.com')
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(0, len(pending_jobs))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_BisectCulpritHasSingleAuthor_AssignsAuthor(self, mock_update_bug):
    # When a bisect finds a single culprit for a perf regression,
    # author and reviewer of the CL should be cc'ed on issue update.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200037, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()

    # Create bug.
    bug_data.Bug(id=12345).put()
    self.testapp.get('/update_bug_with_results')
    mock_update_bug.assert_called_once_with(
        mock.ANY, mock.ANY,
        cc_list=['sullivan@google.com', 'prasadv@google.com'],
        merge_issue=None, labels=None, owner='sullivan@google.com')
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(0, len(pending_jobs))

  def testBeautifyContent(self):
    # Remove buildbot annotations (@@@), leading and trailing spaces from bisect
    # results log.
    actual_output = update_bug_with_results._BeautifyContent(
        _BISECT_LOG_SINGLE_OWNER)
    self.assertNotIn('@@@', actual_output)
    for line in actual_output.split('\n'):
      self.assertFalse(line.startswith(' '))
      self.assertFalse(line.endswith(' '))
    self.assertEqual(_EXPECTED_BISECT_LOG_SINGLE_OWNER, actual_output)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_FailedRevisionResponse(self, mock_add_bug):
    # When a Rietveld CL link fails to respond, only update CL owner in CC list.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200038, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()

    # Create bug.
    bug_data.Bug(id=12345).put()
    self.testapp.get('/update_bug_with_results')
    mock_add_bug.assert_called_once_with(mock.ANY,
                                         mock.ANY,
                                         cc_list=['sullivan@google.com'],
                                         merge_issue=None,
                                         labels=None,
                                         owner='sullivan@google.com')
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(0, len(pending_jobs))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_MergesBugIntoExistingBug(self, mock_update_bug):
    # When there exists a bug with the same revision (commit hash),
    # mark bug as duplicate and merge current issue into that.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200037, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    try_job.TryJob(
        bug_id=54321, rietveld_issue_id=200037, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()

    # Create bug.
    bug_data.Bug(id=12345).put()
    bug_data.Bug(id=54321).put()
    self.testapp.get('/update_bug_with_results')
    # Owners of CLs are not cc'ed for duplicate bugs and the issue should be
    # marked as duplicate.
    mock_update_bug.assert_called_with(mock.ANY,
                                       mock.ANY,
                                       cc_list=[],
                                       merge_issue='12345',
                                       labels=None,
                                       owner=None)
    pending_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(0, len(pending_jobs))
    # Add anomalies.
    test_keys = map(utils.TestKey, [
        'ChromiumGPU/linux-release/scrolling-benchmark/first_paint',
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time'])
    anomaly.Anomaly(
        start_revision=9990, end_revision=9997, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=12345).put()
    anomaly.Anomaly(
        start_revision=9990, end_revision=9996, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=54321).put()
    # Map anomalies to base(dest_bug_id) bug.
    update_bug_with_results._MapAnomaliesToMergeIntoBug(
        dest_bug_id=12345, source_bug_id=54321)
    anomalies = anomaly.Anomaly.query(
        anomaly.Anomaly.bug_id == int(54321)).fetch()
    self.assertEqual(0, len(anomalies))

  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment', mock.MagicMock())
  @mock.patch.object(
      update_bug_with_results, '_GetBisectResults',
      mock.MagicMock(return_value={
          'results': 'Status: Positive\nCommit  : abcd123',
          'status': 'Completed',
          'bisect_bot': 'bar',
          'issue_url': 'bar',
          'buildbot_log_url': 'bar',
      }))
  def testGet_PositiveResult_StoresCommitHash(self):
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    self.testapp.get('/update_bug_with_results')
    self.assertEqual('12345', layered_cache.Get('commit_hash_abcd123'))

  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment', mock.MagicMock())
  @mock.patch.object(
      update_bug_with_results, '_GetBisectResults',
      mock.MagicMock(return_value={
          'results': 'Status: Negative\nCommit  : a121212',
          'status': 'Completed',
          'bisect_bot': 'bar',
          'issue_url': 'bar',
          'buildbot_log_url': 'bar',
      }))
  def testGet_NegativeResult_StoresCommitHash(self):
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()
    self.testapp.get('/update_bug_with_results')
    self.assertIsNone(layered_cache.Get('commit_hash_a121212'))

  def testMapAnomaliesToMergeIntoBug(self):
    # Add anomalies.
    test_keys = map(utils.TestKey, [
        'ChromiumGPU/linux-release/scrolling-benchmark/first_paint',
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time'])
    anomaly.Anomaly(
        start_revision=9990, end_revision=9997, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=12345).put()
    anomaly.Anomaly(
        start_revision=9990, end_revision=9996, test=test_keys[0],
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=None, bug_id=54321).put()
    # Map anomalies to base(dest_bug_id) bug.
    update_bug_with_results._MapAnomaliesToMergeIntoBug(
        dest_bug_id=12345, source_bug_id=54321)
    anomalies = anomaly.Anomaly.query(
        anomaly.Anomaly.bug_id == int(54321)).fetch()
    self.assertEqual(0, len(anomalies))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(update_bug_with_results, '_LogBisectInfraFailure')
  def testCheckBisectBotForInfraFailure_BotFailure(
      self, log_bisect_failure_mock):
    bug_id = 516
    build_data = {
        'steps': [{'name': 'A', 'results': [0]},
                  {'name': 'B', 'results': [2]}],
        'times': [1411501756, 1411545237],
    }
    build_url = 'http://build.chromium.org/builders/516'
    update_bug_with_results._CheckBisectBotForInfraFailure(
        bug_id, build_data, build_url)
    log_bisect_failure_mock.assert_called_with(
        bug_id, 'Bot failure.', mock.ANY)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(update_bug_with_results, '_LogBisectInfraFailure')
  def testCheckBisectBotForInfraFailure_BuildFailure(
      self, log_bisect_failure_mock):
    bug_id = 516
    build_data = {
        'steps': [{'name': 'A', 'results': [0]},
                  {'name': 'slave_steps', 'results': [2]}],
        'times': [1411500000, 1411501000],
    }
    build_url = 'http://build.chromium.org/builders/516'
    update_bug_with_results._CheckBisectBotForInfraFailure(
        bug_id, build_data, build_url)
    log_bisect_failure_mock.assert_called_with(
        bug_id, 'Build failure.', mock.ANY)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_BotInfoInBisectResults(self, mock_update_bug):
    # When a bisect finds multiple culprits by same Author for a perf
    # regression, owner of CLs should be cc'ed.
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200037, rietveld_patchset_id=1,
        status='started', bot='win_perf').put()

    # Create bug.
    bug_data.Bug(id=12345).put()
    self.testapp.get('/update_bug_with_results')
    mock_update_bug.assert_called_once_with(
        12345,
        _EXPECTED_BISECT_RESULTS_ON_BUG,
        cc_list=['sullivan@google.com', 'prasadv@google.com'],
        merge_issue=None,
        labels=None,
        owner='sullivan@google.com')

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results, '_SendPerfTryJobEmail',
      mock.MagicMock(side_effect=_MockSendPerfTryJobEmail))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  def testGet_PerfTryJob(self):
    try_job.TryJob(
        rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf', email='just@atestemail.com',
        job_type='perf-try', config=_PERF_TEST_CONFIG).put()
    global _TEST_RECEIEVED_EMAIL_RESULTS
    _TEST_RECEIEVED_EMAIL_RESULTS = None

    self.testapp.get('/update_bug_with_results')

    results = _TEST_RECEIEVED_EMAIL_RESULTS
    self.assertEqual('Completed', results['status'])
    self.assertEqual(2, len(results['profiler_results']))
    self.assertEqual(_PERF_LOG_EXPECTED_HTML_LINK,
                     results['html_results'])
    self.assertEqual(_PERF_LOG_EXPECTED_TITLE_1,
                     results['profiler_results'][0][0])
    self.assertEqual(_PERF_LOG_EXPECTED_PROFILER_LINK1,
                     results['profiler_results'][0][1])
    self.assertEqual(_PERF_LOG_EXPECTED_TITLE_2,
                     results['profiler_results'][1][0])
    self.assertEqual(_PERF_LOG_EXPECTED_PROFILER_LINK2,
                     results['profiler_results'][1][1])
    self.assertEqual('win_perf_bisect', results['bisect_bot'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results, '_SendPerfTryJobEmail',
      mock.MagicMock(side_effect=_MockSendPerfTryJobEmail))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  def testGet_PerfTryJobWithInvalidOutput_EmailResultsAreEmpty(self):
    try_job.TryJob(
        rietveld_issue_id=200035, rietveld_patchset_id=1,
        status='started', bot='win_perf', email='just@atestemail.com',
        job_type='perf-try', config=_PERF_TEST_CONFIG).put()
    global _TEST_RECEIEVED_EMAIL_RESULTS
    _TEST_RECEIEVED_EMAIL_RESULTS = None

    self.testapp.get('/update_bug_with_results')

    results = _TEST_RECEIEVED_EMAIL_RESULTS
    self.assertEqual('Completed', results['status'])
    self.assertEqual(0, len(results['profiler_results']))
    self.assertEqual('', results['html_results'])
    self.assertEqual('win_perf_bisect', results['bisect_bot'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch(
      'google.appengine.api.mail.send_mail',
      mock.MagicMock(side_effect=_MockSendMail))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  def testGet_CreatePerfSuccessEmail(self):
    try_job.TryJob(
        rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf', email='just@atestemail.com',
        job_type='perf-try', config=_PERF_TEST_CONFIG).put()
    global _TEST_RECEIVED_EMAIL
    _TEST_RECEIVED_EMAIL = {}

    self.testapp.get('/update_bug_with_results')

    self.assertIn('<a href="http://build.chromium.org/508">'
                  'http://build.chromium.org/508</a>.',
                  _TEST_RECEIVED_EMAIL.get('html'))
    self.assertIn('With Patch', _TEST_RECEIVED_EMAIL.get('body'))
    self.assertIn('Without Patch', _TEST_RECEIVED_EMAIL.get('body'))
    self.assertIn('just@atestemail.com',
                  _TEST_RECEIVED_EMAIL.get('to'))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch(
      'google.appengine.api.mail.send_mail',
      mock.MagicMock(side_effect=_MockSendMail))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service, 'IssueTrackerService',
      mock.MagicMock())
  def testGet_CreatePerfFailureEmail(self):
    try_job.TryJob(
        rietveld_issue_id=200034, rietveld_patchset_id=1,
        status='started', bot='win_perf', email='just@atestemail.com',
        job_type='perf-try').put()

    global _TEST_RECEIVED_EMAIL
    _TEST_RECEIVED_EMAIL = {}

    self.testapp.get('/update_bug_with_results')

    self.assertIn('Perf Try Job FAILURE\n<br>',
                  _TEST_RECEIVED_EMAIL.get('html'))
    self.assertIn('Perf Try Job FAILURE\n\n',
                  _TEST_RECEIVED_EMAIL.get('body'))
    self.assertIn('just@atestemail.com',
                  _TEST_RECEIVED_EMAIL.get('to'))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  @mock.patch.object(
      update_bug_with_results, '_RietveldIssueJSONURL',
      mock.MagicMock(
          return_value='https://test-rietveld.appspot.com/api/200037/1'))
  @mock.patch.object(
      update_bug_with_results.issue_tracker_service.IssueTrackerService,
      'AddBugComment')
  def testGet_InternalOnlyTryJob_AddsInternalOnlyBugLabel(
      self, mock_update_bug):
    try_job.TryJob(
        bug_id=12345, rietveld_issue_id=200037, rietveld_patchset_id=1,
        status='started', bot='win_perf', internal_only=True).put()
    # Create bug.
    bug_data.Bug(id=12345).put()
    self.testapp.get('/update_bug_with_results')
    mock_update_bug.assert_called_once_with(
        mock.ANY, mock.ANY,
        cc_list=mock.ANY,
        merge_issue=None, labels=['Restrict-View-Google'], owner=mock.ANY)

  def testValidateAndConvertBuildbucketResponse_NoResults(self):
    buildbucket_response_scheduled = r"""{
      "build": {
        "status": "SCHEDULED",
        "id": "9043191319901995952"
      }
    }"""
    with self.assertRaises(update_bug_with_results.UnexpectedJsonError):
      update_bug_with_results._ValidateAndConvertBuildbucketResponse(
          json.loads(buildbucket_response_scheduled))

  def testValidateAndConvertBuildbucketResponse_Failed(self):
    buildbucket_response_failed = r"""{
      "build": {
        "status": "COMPLETED",
        "url": "http://build.chromium.org/linux_perf_bisector/builds/41",
        "failure_reason": "BUILD_FAILURE",
        "result": "FAILURE",
        "id": "9043547105089652704"
      }
    }"""
    converted_response = (
        update_bug_with_results._ValidateAndConvertBuildbucketResponse(
            json.loads(buildbucket_response_failed)))
    self.assertIn('http', converted_response['url'])
    self.assertEqual(converted_response['result'],
                     update_bug_with_results.FAILURE)

  def testValidateAndConvertBuildbucketResponse_Success(self):
    buildbucket_response_success = r"""{
      "build": {
       "status": "COMPLETED",
       "url": "http://build.chromium.org/linux_perf_bisector/builds/47",
       "id": "9043278384371361584",
       "result": "SUCCESS"
      }
    }"""
    converted_response = (
        update_bug_with_results._ValidateAndConvertBuildbucketResponse(
            json.loads(buildbucket_response_success)))
    self.assertIn('http', converted_response['url'])
    self.assertEqual(converted_response['result'],
                     update_bug_with_results.SUCCESS)

if __name__ == '__main__':
  unittest.main()
