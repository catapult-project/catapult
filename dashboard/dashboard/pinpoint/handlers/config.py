# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.pinpoint.models import bot_configurations


class Config(webapp2.RequestHandler):
  """Handler returning site configuration details."""

  def get(self):
    self.response.out.write(json.dumps({
        'configurations': bot_configurations.List(),
    }))
