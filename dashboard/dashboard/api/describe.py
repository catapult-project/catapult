# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard import update_test_suite_descriptors
from dashboard.api import api_request_handler


class DescribeHandler(api_request_handler.ApiRequestHandler):
  """API handler for describing test suites."""

  def _AllowAnonymous(self):
    return True

  def PrivilegedPost(self, *args):
    return self.UnprivilegedPost(*args)

  def UnprivilegedPost(self, *args):
    return update_test_suite_descriptors.FetchCachedTestSuiteDescriptor(args[0])
