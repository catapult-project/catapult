# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint import test


class StatsTest(test.TestCase):

  def testPost_ValidRequest(self):
    # Create job.
    job = job_module.Job.New((), ())

    data = json.loads(self.testapp.get('/api/stats').body)

    expected = [{
        'comparison_mode': None,
        'completed': True,
        'created': job.created.isoformat(),
        'difference_count': None,
        'failed': False,
        'updated': job.updated.isoformat(),
    }]
    self.assertEqual(data, expected)
