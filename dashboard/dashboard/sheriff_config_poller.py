# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Polls the sheriff_config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from dashboard.common import request_handler
from dashboard.sheriff_config_client import SheriffConfigClient
import webapp2


class ConfigsUpdateHandler(request_handler.RequestHandler):
  """Handles the cron job request to poll the sheriff-config service."""

  def get(self):
    client = SheriffConfigClient()
    ok, err_msg = client.Update()
    if not ok:
      return webapp2.Response('FAILED: %s' % err_msg)
    return webapp2.Response('OK')
