# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import webapp2
import webtest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.handlers import list_jobs


class ListJobsTest(unittest.TestCase):

  def setUp(self):
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/list_jobs', list_jobs.ListJobsHandler),
    ])
    self.testapp = webtest.TestApp(app)
    self.testapp.extra_environ.update({'REMOTE_ADDR': 'remote_ip'})

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testPost_ValidRequest(self):
    # Create job.
    job = job_module.Job.New(
        configuration='configuration',
        test_suite='suite',
        test='filter',
        metric='metric',
        auto_explore=True)
    job.put()

    data = json.loads(self.testapp.post('/list_jobs').body)

    self.assertEqual(1, data['jobs_count'])
    self.assertEqual(1, len(data['jobs_list']))
    self.assertEqual(job.AsDict(), data['jobs_list'][0])
