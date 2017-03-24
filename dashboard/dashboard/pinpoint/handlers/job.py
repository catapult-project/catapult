# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.pinpoint.models import job as job_module


class JobHandler(webapp2.RequestHandler):

  def post(self):
    job_id = self.request.get('job_id')

    # Validate parameters.
    try:
      job = job_module.JobFromId(job_id)
    except Exception as e:  # pylint: disable=broad-except
      # Catching google.net.proto.ProtocolBuffer.ProtocolBufferDecodeError
      # directly doesn't work.
      # https://github.com/googlecloudplatform/datastore-ndb-python/issues/143
      if e.__class__.__name__ == 'ProtocolBufferDecodeError':
        self.response.write(json.dumps({'error': 'Unknown job id.'}))
        return
      raise

    self.response.write(json.dumps({'data': job.AsDict()}))
