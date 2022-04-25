# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.pinpoint.models import scheduler
from dashboard.common import utils

if utils.IsRunningFlask():
  from flask import make_response
else:
  import webapp2

if utils.IsRunningFlask():

  def QueueStatsHandlerGet(configuration):
    if not configuration:
      return make_response(
          json.dumps({'error': 'Missing configuration in request.'}), 400)

    queue_stats = scheduler.QueueStats(configuration)
    return make_response(json.dumps(queue_stats))
else:

  class QueueStats(webapp2.RequestHandler):

    def get(self, configuration):
      if not configuration:
        self.response.set_status(400)
        self.response.write(
            json.dumps({'error': 'Missing configuration in request.'}))
        return

      queue_stats = scheduler.QueueStats(configuration)
      self.response.write(json.dumps(queue_stats))
