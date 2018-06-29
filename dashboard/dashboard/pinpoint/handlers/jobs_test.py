# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

from dashboard.pinpoint.handlers import jobs
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint import test


class JobsTest(test.TestCase):

  @mock.patch.object(jobs.utils, 'GetEmail', mock.MagicMock(return_value=None))
  def testGet_NoUser(self):
    job = job_module.Job.New((), ())

    data = json.loads(self.testapp.get('/api/jobs?o=STATE').body)

    self.assertEqual(1, data['count'])
    self.assertEqual(1, len(data['jobs']))
    self.assertEqual(job.AsDict([job_module.OPTION_STATE]), data['jobs'][0])

  @mock.patch.object(jobs.utils, 'GetEmail',
                     mock.MagicMock(return_value='lovely.user@example.com'))
  def testGet_WithUser(self):
    job_module.Job.New((), ())
    job_module.Job.New((), (), user='lovely.user@example.com')
    job = job_module.Job.New((), (), user='lovely.user@example.com')

    data = json.loads(self.testapp.get('/api/jobs?o=STATE').body)

    self.assertEqual(2, data['count'])
    self.assertEqual(2, len(data['jobs']))

    sorted_data = sorted(data['jobs'], key=lambda d: d['job_id'])
    self.assertEqual(job.AsDict([job_module.OPTION_STATE]), sorted_data[-1])
