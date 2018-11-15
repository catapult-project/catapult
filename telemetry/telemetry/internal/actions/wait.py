# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry.internal.actions import page_action

import py_utils

class WaitForElementAction(page_action.ElementPageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               timeout_in_seconds=60):
    super(WaitForElementAction, self).__init__(selector, text, element_function)
    self._timeout_in_seconds = timeout_in_seconds

  def RunAction(self, tab):
    code = 'function(element) { return element != null; }'
    try:
      self.EvaluateCallback(tab, code, wait=True,
                            timeout_in_seconds=self._timeout_in_seconds)
    except py_utils.TimeoutException as e:
      # Rethrow with the original stack trace for better debugging.
      raise py_utils.TimeoutException, \
          py_utils.TimeoutException(
              'Timeout while waiting for element.\n' + e.message), \
          sys.exc_info()[2]
