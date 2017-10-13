# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job


_CHROMIUM_URL = 'https://chromium.googlesource.com/chromium/src'


_COMMENT_STARTED = (
    u"""\U0001f4cd Pinpoint job started.
https://testbed.example.com/job/1""")


_COMMENT_COMPLETED_NO_DIFFERENCES = (
    u"""<b>\U0001f4cd Couldn't reproduce a difference.</b>
https://testbed.example.com/job/1""")


_COMMENT_COMPLETED_ONE_DIFFERENCE = (
    u"""<b>\U0001f4cd Found a significant difference after 1 commit.</b>
https://testbed.example.com/job/1

<b>Subject.</b>
By author@chromium.org \xb7 Fri Jan 01 00:01:00 2016
chromium @ git_hash

Understanding performance regressions:
  http://g.co/ChromePerformanceRegressions""")


_COMMENT_COMPLETED_TWO_DIFFERENCES = (
    u"""<b>\U0001f4cd Found significant differences after each of 2 commits.</b>
https://testbed.example.com/job/1

<b>Subject.</b>
By author1@chromium.org \xb7 Fri Jan 01 00:01:00 2016
chromium @ git_hash_1

<b>Subject.</b>
By author2@chromium.org \xb7 Fri Jan 02 00:01:00 2016
chromium @ git_hash_2

Understanding performance regressions:
  http://g.co/ChromePerformanceRegressions""")


_COMMENT_FAILED = (
    u"""\U0001f63f Pinpoint job stopped with an error.
https://testbed.example.com/job/1""")


@mock.patch('dashboard.common.utils.ServiceAccountHttp', mock.MagicMock())
class BugCommentTest(testing_common.TestCase):

  def setUp(self):
    super(BugCommentTest, self).setUp()

    self.add_bug_comment = mock.MagicMock()
    patcher = mock.patch('dashboard.services.issue_tracker_service.'
                         'IssueTrackerService')
    issue_tracker_service = patcher.start()
    issue_tracker_service.return_value = mock.MagicMock(
        AddBugComment=self.add_bug_comment)
    self.addCleanup(patcher.stop)

    namespaced_stored_object.Set('repositories', {
        'chromium': {'repository_url': _CHROMIUM_URL},
    })

  def tearDown(self):
    self.testbed.deactivate()

  def testNoBug(self):
    j = job.Job.New({}, [], False)
    j.put()
    j.Start()
    j.Run()

    self.assertFalse(self.add_bug_comment.called)

  def testStarted(self):
    j = job.Job.New({}, [], False, bug_id=123456)
    j.put()
    j.Start()

    self.add_bug_comment.assert_called_once_with(
        123456, _COMMENT_STARTED, send_email=False)

  def testCompletedNoDifference(self):
    j = job.Job.New({}, [], False, bug_id=123456)
    j.put()
    j.Run()

    self.add_bug_comment.assert_called_once_with(
        123456, _COMMENT_COMPLETED_NO_DIFFERENCES)

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  @mock.patch.object(job._JobState, 'Differences')
  def testCompletedOneDifference(self, differences, commit_info):
    c = change.Change((change.Commit('chromium', 'git_hash'),))
    differences.return_value = [(1, c)]
    commit_info.return_value = {
        'author': {'email': 'author@chromium.org'},
        'committer': {'time': 'Fri Jan 01 00:01:00 2016'},
        'message': 'Subject.\n\n'
                   'Commit message.\n'
                   'Reviewed-by: Reviewer Name <reviewer@chromium.org>',
    }

    j = job.Job.New({}, [], False, bug_id=123456)
    j.put()
    j.Run()

    self.add_bug_comment.assert_called_once_with(
        123456, _COMMENT_COMPLETED_ONE_DIFFERENCE,
        status='Assigned', owner='author@chromium.org',
        cc_list=['author@chromium.org', 'reviewer@chromium.org'])

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  @mock.patch.object(job._JobState, 'Differences')
  def testCompletedMultipleDifferences(self, differences, commit_info):
    c1 = change.Change((change.Commit('chromium', 'git_hash_1'),))
    c2 = change.Change((change.Commit('chromium', 'git_hash_2'),))
    differences.return_value = [(1, c1), (2, c2)]
    commit_info.side_effect = (
        {
            'author': {'email': 'author1@chromium.org'},
            'committer': {'time': 'Fri Jan 01 00:01:00 2016'},
            'message': 'Subject.\n\n'
                       'Commit message.\n'
                       'Reviewed-by: Reviewer Name <reviewer1@chromium.org>',
        },
        {
            'author': {'email': 'author2@chromium.org'},
            'committer': {'time': 'Fri Jan 02 00:01:00 2016'},
            'message': 'Subject.\n\n'
                       'Commit message.\n'
                       'Reviewed-by: Reviewer Name <reviewer1@chromium.org>\n'
                       'Reviewed-by: Reviewer Name <reviewer2@chromium.org>',
        },
    )

    j = job.Job.New({}, [], False, bug_id=123456)
    j.put()
    j.Run()

    self.add_bug_comment.assert_called_once_with(
        123456, _COMMENT_COMPLETED_TWO_DIFFERENCES,
        status='Assigned', owner='author2@chromium.org',
        cc_list=['author1@chromium.org', 'author2@chromium.org',
                 'reviewer1@chromium.org', 'reviewer2@chromium.org'])

  def testFailed(self):
    j = job.Job.New({}, [], False, bug_id=123456)
    j.put()
    j.state = None  # No state object is an AttributeError.
    with self.assertRaises(AttributeError):
      j.Run()

    self.add_bug_comment.assert_called_once_with(123456, _COMMENT_FAILED)
