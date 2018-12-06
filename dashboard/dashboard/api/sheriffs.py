# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.api import api_request_handler
from dashboard.models import sheriff


class SheriffsHandler(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    pass

  def Post(self):
    sheriff_keys = sheriff.Sheriff.query().fetch(keys_only=True)
    return [key.string_id() for key in sheriff_keys]
