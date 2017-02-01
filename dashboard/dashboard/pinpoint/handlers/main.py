# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for displaying an overview of Pinpoint."""

from dashboard.pinpoint import request_handler


class MainHandler(request_handler.RequestHandler):
  """Shows the main overview for Pinpoint."""

  def get(self):
    """Renders the UI for main overview page."""
    self.RenderStaticHtml('main.html')
