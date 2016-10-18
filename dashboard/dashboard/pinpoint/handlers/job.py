# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from dashboard.pinpoint.models import job as job_module


class JobHandler(webapp2.RequestHandler):

  def get(self, job_id):
    # Validate parameters.
    try:
      job = job_module.JobFromId(job_id)
    except:  # pylint: disable=bare-except
      # There's no narrower exception we can catch. Catching
      # google.net.proto.ProtocolBuffer.ProtocolBufferDecodeError
      # doesn't appear to work here.
      # https://github.com/googlecloudplatform/datastore-ndb-python/issues/143
      self.response.write('Unknown job id.')
      return

    # Generate an excellent Polymer UI.
    # TODO: This.
    del job

  def post(self):
    pass  # TODO: Allow modifications to the job.
