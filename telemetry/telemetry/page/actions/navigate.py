# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action

class NavigateAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(NavigateAction, self).__init__(attributes)

  def RunAction(self, page, tab):
    if page.is_file:
      target_side_url = tab.browser.http_server.UrlOf(page.file_path_url)
    else:
      target_side_url = page.url

    tab.Navigate(target_side_url, page.script_to_evaluate_on_commit)
    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
