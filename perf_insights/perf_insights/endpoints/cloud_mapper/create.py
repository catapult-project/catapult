# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import uuid
import webapp2

from google.appengine.api import taskqueue
from perf_insights.endpoints.cloud_mapper import job_info

class CreatePage(webapp2.RequestHandler):

  def post(self):
    self.response.headers['Content-Type'] = 'text/plain'

    mapper = self.request.get('mapper')
    reducer = self.request.get('reducer')
    mapper_function = self.request.get('mapper_function')
    query = self.request.get('query')
    corpus = self.request.get('corpus')
    revision = self.request.get('revision')
    if not revision:
      revision = 'HEAD'

    job_uuid = str(uuid.uuid4())
    logging.info('Creating new job %s' % job_uuid)
    job = job_info.JobInfo(id=job_uuid)
    job.remote_addr = os.environ["REMOTE_ADDR"]
    job.status = 'QUEUED'
    job.mapper = mapper
    job.reducer = reducer
    job.mapper_function = mapper_function
    job.query = query
    job.corpus = corpus
    job.revision = revision
    job.put()

    response = {
        'status': True,
        'jobid': job_uuid
    }

    self.response.out.write(json.dumps(response))

    payload = {'jobid': job_uuid, 'type': 'create'}
    taskqueue.add(url='/cloud_mapper/task', name=job_uuid, params=payload)


app = webapp2.WSGIApplication([('/cloud_mapper/create', CreatePage)])
