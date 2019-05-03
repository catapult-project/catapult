# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard import update_test_suites
from dashboard.api import api_request_handler


class TestSuitesHandler(api_request_handler.ApiRequestHandler):
  """API handler for listing test suites."""

  def _CheckUser(self):
    pass

  def Post(self):
    return update_test_suites.FetchCachedTestSuites2()
