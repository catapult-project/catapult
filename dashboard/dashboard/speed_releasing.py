# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the speed releasing table."""

import json

from dashboard.common import request_handler


class SpeedReleasingHandler(request_handler.RequestHandler):
  """Request handler for requests for speed releasing page."""

  def get(self):
    """Renders the UI for the speed releasing page."""
    self.RenderStaticHtml('speed_releasing.html')

  def post(self):
    """Returns dynamic data for /speed_releasing.

    Outputs:
      JSON for the /speed_releasing page XHR request.
    """
    values = {}
    self.GetDynamicVariables(values)
    self.response.out.write(json.dumps({
        'xsrf_token': values['xsrf_token'],
    }))
