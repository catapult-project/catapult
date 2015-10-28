# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides an interface to manually put a buildbucket job."""

import json

from dashboard import buildbucket_job
from dashboard import buildbucket_service
from dashboard import request_handler
from dashboard import utils


class TestBuildbucketHandler(request_handler.RequestHandler):

  def get(self):
    self.RenderHtml('put_buildbucket_job.html', {})

  def post(self):
    if not utils.IsInternalUser():
      self.response.out.write(json.dumps({
          'error': 'You are not authorized to post to this endpoint.',
      }))
      return
    job = buildbucket_job.BisectJob(
        'linux_perf_bisector',
        self.request.get('good_revision'),
        self.request.get('bad_revision'),
        self.request.get('command'),
        self.request.get('metric'),
        self.request.get('repeat_count'),
        self.request.get('max_time_minutes'),
        self.request.get('bug_id'),
        self.request.get('gs_bucket'),
        self.request.get('recipe_tester_name'),
        self.request.get('builder_host'),
        self.request.get('builder_port'))

    buildbucket_service.PutJob(job)
    self.response.out.write(job.response_fields)
