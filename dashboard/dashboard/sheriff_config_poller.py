# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Polls the sheriff_config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from dashboard.common import request_handler
from oauth2client import appengine
import httplib2
import webapp2


class ConfigsUpdateHandler(request_handler.RequestHandler):
  """Handles the cron job request to poll the sheriff-config service."""

  def get(self):
    """Make the Cloud Endpoints request from this handler."""
    credentials = appengine.AppAssertionCredentials(
        scope='https://www.googleapis.com/auth/userinfo.email')
    http = credentials.authorize(httplib2.Http())
    (response, content) = http.request(
        'https://sheriff-config-dot-chromeperf.appspot.com/configs/update',
        'GET')
    if response.status != '200':
      return webapp2.Response('FAILED: %r\n%s' % (response, content))
    return webapp2.Response('OK')
