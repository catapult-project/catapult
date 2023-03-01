# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import json
import mock

from dashboard.pinpoint import test
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import results2 as results2_module


@mock.patch('dashboard.services.swarming.GetAliveBotsByDimensions',
            mock.MagicMock(return_value=["a"]))
@mock.patch('dashboard.common.cloud_metric._PublishTSCloudMetric',
            mock.MagicMock())
class JobTest(test.TestCase):

  @mock.patch.object(results2_module, 'GetCachedResults2', return_value="")
  def testGet_NotStarted(self, _):
    job = job_module.Job.New((), ())
    data = json.loads(self.testapp.get('/api/job/' + job.job_id).body)
    self.assertEqual(job.created.isoformat(), data['created'])

  @mock.patch.object(results2_module, 'GetCachedResults2', return_value="")
  def testGet_Started(self, _):
    job = job_module.Job.New((), ())
    job.started = True
    job.started_time = datetime.datetime.utcnow()
    job.put()

    data = json.loads(self.testapp.get('/api/job/' + job.job_id).body)
    self.assertEqual(job.started_time.isoformat(), data['started_time'])
