# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from google.appengine.api import users


class Login(webapp2.RequestHandler):
  """XHR endpoint to login."""

  def post(self):
    request_path = self.request.get('path')
    user = users.get_current_user()

    result = {}
    if user:
      result['display_username'] = user.email()

    result['login_url'] = users.create_login_url(
        request_path or self.request.path_qs)

    self.response.out.write(json.dumps(result))
