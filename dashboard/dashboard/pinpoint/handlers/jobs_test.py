# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import webapp2
import webtest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.pinpoint.handlers import jobs
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import quest_generator


class JobsTest(unittest.TestCase):

  def setUp(self):
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/jobs', jobs.Jobs),
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
    generator = quest_generator.QuestGenerator({
        'configuration': 'chromium-rel-mac11-pro',
        'target': 'telemetry_perf_tests',
        'dimensions': '{}',
        'benchmark': 'speedometer',
    })
    job = job_module.Job.New(
        arguments=generator.AsDict(),
        quests=generator.Quests(),
        auto_explore=True,
        bug_id=None)
    job.put()

    data = json.loads(self.testapp.post('/jobs').body)

    self.assertEqual(1, data['jobs_count'])
    self.assertEqual(1, len(data['jobs_list']))
    self.assertEqual(job.AsDict(), data['jobs_list'][0])
