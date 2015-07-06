# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for reporting a graph of traces."""

__author__ = 'sullivan@google.com (Annie Sullivan)'

import json
import os

from dashboard import chart_handler
from dashboard import update_test_suites


class ReportHandler(chart_handler.ChartHandler):

  def get(self):
    """Renders the UI for selecting graphs."""
    dev_version = ('Development' in os.environ['SERVER_SOFTWARE'] or
                   self.request.host == 'chrome-perf.googleplex.com')
    self.RenderHtml('report.html', {
        'dev_version': dev_version,
        'test_suites': json.dumps(update_test_suites.FetchCachedTestSuites()),
    })
