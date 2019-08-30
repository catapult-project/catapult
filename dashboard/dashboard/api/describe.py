# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard import update_test_suite_descriptors
from dashboard.api import api_request_handler


class DescribeHandler(api_request_handler.ApiRequestHandler):
  """API handler for describing test suites."""

  def _CheckUser(self):
    pass

  def Post(self):
    master = self.request.get('master')
    suite = self.request.get('test_suite')
    return update_test_suite_descriptors.FetchCachedTestSuiteDescriptor(
        master, suite)
