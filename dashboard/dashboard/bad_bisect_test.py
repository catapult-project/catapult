# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
import webtest

# pylint: disable=unused-import
from dashboard import mock_oauth2_decorator
# pylint: enable=unused-import

from google.appengine.api import users

from dashboard import bad_bisect
from dashboard import quick_logger
from dashboard import testing_common
from dashboard import xsrf
from dashboard.models import try_job


class BadBisectHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(BadBisectHandlerTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/bad_bisect',
         bad_bisect.BadBisectHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetSheriffDomains(['chromium.org'])
    testing_common.SetIsInternalUser('test@chromium.com', True)
    self.SetCurrentUser('test@chromium.org')
    try_job.TryJob(id=1234).put()

  def testGet_WithNoTryJobId_ShowsError(self):
    response = self.testapp.get('/bad_bisect')
    self.assertIn('<h1 class="error">', response.body)

  def testGet_NotLoggedIn_ShowsError(self):
    self.UnsetCurrentUser()
    self.testapp.get('/bad_bisect?', {'try_job_id': '1234'})
    response = self.testapp.get('/bad_bisect')
    self.assertEqual(302, response.status_code)

  def testGet_RenderForm(self):
    response = self.testapp.get('/bad_bisect?', {'try_job_id': '1234'})
    self.assertEqual(1, len(response.html('form')))
    self.assertIn('1234', response.body)

  def testPost_FeedbackRecorded(self):
    self.testapp.post('/bad_bisect?', {
        'try_job_id': '1234',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    jobs = try_job.TryJob.query().fetch()
    self.assertEqual(1, len(jobs))
    self.assertEqual({'test@chromium.org'}, jobs[0].bad_result_emails)

  def testPost_LogAdded(self):
    self.testapp.post('/bad_bisect?', {
        'try_job_id': '1234',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    logs = quick_logger.Get('bad_bisect', 'report')
    self.assertEqual(1, len(logs))
