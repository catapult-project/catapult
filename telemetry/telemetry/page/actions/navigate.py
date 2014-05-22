# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page.actions import page_action


class NavigateAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(NavigateAction, self).__init__(attributes)
    assert hasattr(self, 'url'), 'Must specify url for navigate action'

  def RunAction(self, tab):
    script_to_evaluate_on_commit = None
    if hasattr(self, 'script_to_evaluate_on_commit'):
      script_to_evaluate_on_commit = getattr(self,
                                             'script_to_evaluate_on_commit')
    if hasattr(self, 'timeout_seconds') and self.timeout_seconds:
      tab.Navigate(self.url,
                   script_to_evaluate_on_commit,
                   self.timeout_seconds)
    else:
      tab.Navigate(self.url, script_to_evaluate_on_commit)
    tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
