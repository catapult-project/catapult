# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint containing server-side functionality for pinpoint jobs."""

import json

from google.appengine.api import users

from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.services import pinpoint_service

_PINPOINT_URL = 'https://pinpoint-dot-chromeperf.appspot.com/api/new'


class PinpointNewRequestHandler(request_handler.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if not utils.IsValidSheriffUser():
      message = 'User "%s" not authorized.' % user
      self.response.out.write(json.dumps({'error': message}))
      return

    job_params = dict(
        (a, self.request.get(a)) for a in self.request.arguments())
    job_params['email'] = user.email()

    self.response.write(json.dumps(pinpoint_service.NewJob(job_params)))
