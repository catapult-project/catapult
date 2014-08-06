# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page import page_test


class PageMeasurement(page_test.PageTest):
  """DEPRECATED: Please extend page_test.PageTest directly."""
  def __init__(self,
               action_name_to_run='',
               needs_browser_restart_after_each_page=False,
               discard_first_result=False,
               clear_cache_before_each_run=False,
               is_action_name_to_run_optional=False):
    super(PageMeasurement, self).__init__(
      action_name_to_run,
      needs_browser_restart_after_each_page,
      discard_first_result,
      clear_cache_before_each_run,
      is_action_name_to_run_optional=is_action_name_to_run_optional)
