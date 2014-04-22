# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import page_action
from telemetry.page.actions import wait
from telemetry import decorators

class GestureAction(page_action.PageAction):
  def __init__(self, attributes=None):
    super(GestureAction, self).__init__(attributes)
    if hasattr(self, 'wait_after'):
      self.wait_action = wait.WaitAction(self.wait_after)
    else:
      self.wait_action = None

    assert self.wait_until is None or self.wait_action is None, '''gesture
cannot have wait_after and wait_until at the same time.'''


  def RunAction(self, page, tab):
    self.RunGesture(page, tab)
    if self.wait_action:
      self.wait_action.RunAction(page, tab)

  def RunGesture(self, page, tab):
    raise NotImplementedError()

  @staticmethod
  def GetGestureSourceTypeFromOptions(tab):
    gesture_source_type = tab.browser.synthetic_gesture_source_type
    return 'chrome.gpuBenchmarking.' + gesture_source_type.upper() + '_INPUT'

  @staticmethod
  @decorators.Cache
  def IsGestureSourceTypeSupported(tab, gesture_source_type):
    # TODO(dominikg): remove once support for
    #                 'chrome.gpuBenchmarking.gestureSourceTypeSupported' has
    #                 been rolled into reference build.
    if tab.EvaluateJavaScript("""
        typeof chrome.gpuBenchmarking.gestureSourceTypeSupported ===
            'undefined'"""):
      return True

    return tab.EvaluateJavaScript("""
        chrome.gpuBenchmarking.gestureSourceTypeSupported(
            chrome.gpuBenchmarking.%s_INPUT)"""
        % (gesture_source_type.upper()))
