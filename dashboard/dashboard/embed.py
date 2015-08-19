# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to show a chart with minimal UI."""

from google.appengine.api import users

from dashboard import chart_handler


class EmbedHandler(chart_handler.ChartHandler):

  def get(self):
    """Renders the UI for a simple, embeddable chart.

    Request parameters:
      masters: Comma-separated list of master names.
      bots: Comma-separated list of bot names.
      tests: Comma-separated list of of slash-separated test paths
          (without master/bot).
      rev: Revision number (optional).
      num_points: Number of points to plot (optional).
      start_rev: Starting evision number (optional).
      end_rev: Ending revision number (optional).

    Outputs:
      An HTML page with a chart.
    """
    # TODO(qyearsley): Re-enable embed page. http://crbug.com/521756.
    self.response.out.write(
        'The embed page is temporarily disabled, see http://crbug.com/521756.')
