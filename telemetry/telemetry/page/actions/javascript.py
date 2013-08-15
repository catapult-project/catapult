# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action


class JavascriptAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(JavascriptAction, self).__init__(attributes)

  def RunAction(self, page, tab, previous_action):
    assert hasattr(self, 'expression')
    tab.ExecuteJavaScript(self.expression)