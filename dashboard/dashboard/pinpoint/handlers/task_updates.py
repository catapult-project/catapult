# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import json
import logging
import webapp2


class TaskUpdates(webapp2.RequestHandler):
  """Handle updates received from Pub/Sub on Swarming Tasks."""

  def post(self):
    """Handle push messages including information about the swarming task."""
    # Read the JSON body of the message, as how Pub/Sub will use.
    message = json.load(self.request.body_file)

    # Load the base64-encoded data in the message, which should include the
    # following information:
    #   - job id
    #   - task id
    #   - additional task-specific details
    pinpoint_data = json.loads(
        base64.standard_b64decode(message.get('data', '')))
    logging.debug('Received: %s', pinpoint_data)

    # TODO(dberris): Implement the following in the future version of this
    # handler:
    #  - Load the job given the ID
    #  - Load the task given the ID
    #  - Evaluate the state of the job (maybe deferred)
    return webapp2.Response(status='204 No Content')
