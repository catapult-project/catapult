# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class ActionRunner(object):
  def __init__(self, page, tab, page_test=None):
    self._page = page
    self._tab = tab
    self._page_test = page_test

  def RunAction(self, action):
    if not action.WillWaitAfterRun():
      action.WillRunAction(self._page, self._tab)
    if self._page_test:
      self._page_test.WillRunAction(self._page, self._tab, action)
    try:
      action.RunActionAndMaybeWait(self._page, self._tab)
    finally:
      if self._page_test:
        self._page_test.DidRunAction(self._page, self._tab, action)
