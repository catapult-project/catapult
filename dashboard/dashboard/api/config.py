# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.api import api_request_handler
from dashboard.common import namespaced_stored_object
from dashboard import chart_handler


WHITELIST = [
    chart_handler.REVISION_INFO_KEY,
]


class ConfigHandler(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    pass

  def Post(self):
    key = self.request.get('key')
    if key not in WHITELIST:
      return
    return namespaced_stored_object.Get(key)
