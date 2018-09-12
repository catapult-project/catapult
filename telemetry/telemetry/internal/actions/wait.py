# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from telemetry.internal.actions import page_action

import py_utils

class WaitForElementAction(page_action.PageAction):
  def __init__(self, selector=None, text=None, element_function=None,
               timeout_in_seconds=60):
    super(WaitForElementAction, self).__init__()
    self.selector = selector
    self.text = text
    self.element_function = element_function
    self.timeout_in_seconds = timeout_in_seconds

  def RunAction(self, tab):
    code = 'function(element) { return element != null; }'
    try:
      page_action.EvaluateCallbackWithElement(
          tab, code, selector=self.selector, text=self.text,
          element_function=self.element_function,
          wait=True, timeout_in_seconds=self.timeout_in_seconds)
    except py_utils.TimeoutException as e:
      # Rethrow with the original stack trace for better debugging.
      raise py_utils.TimeoutException, \
          py_utils.TimeoutException(
              'Timeout while waiting for element.\n' + e.message), \
          sys.exc_info()[2]
