# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util

DEFAULT_WEB_CONTENTS_TIMEOUT = 90

# TODO(achuith, dtu, nduca): Add unit tests specifically for WebContents,
# independent of Tab.
class WebContents(object):
  """Represents web contents in the browser"""
  def __init__(self, inspector_backend):
    self._inspector_backend = inspector_backend

    with open(os.path.join(os.path.dirname(__file__),
        'network_quiescence.js')) as f:
      self._quiescence_js = f.read()

  def Close(self):
    """Closes this page.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control."""
    self._inspector_backend.Close()

  def WaitForDocumentReadyStateToBeComplete(self,
      timeout=DEFAULT_WEB_CONTENTS_TIMEOUT):
    self.WaitForJavaScriptExpression(
        'document.readyState == "complete"', timeout)

  def WaitForDocumentReadyStateToBeInteractiveOrBetter(self,
      timeout=DEFAULT_WEB_CONTENTS_TIMEOUT):
    self.WaitForJavaScriptExpression(
        'document.readyState == "interactive" || '
        'document.readyState == "complete"', timeout)

  def WaitForJavaScriptExpression(self, expr, timeout):
    """Waits for the given JavaScript expression to be True.

    This method is robust against any given Evaluation timing out.
    """
    def IsTrue():
      try:
        return bool(self.EvaluateJavaScript(expr))
      except util.TimeoutException:
        # If the main thread is busy for longer than Evaluate's timeout, we
        # may time out here early. Instead, we want to wait for the full
        # timeout of this method.
        return False
    util.WaitFor(IsTrue, timeout)

  def HasReachedQuiescence(self):
    """Determine whether the page has reached quiescence after loading.

    Returns:
      True if 2 seconds have passed since last resource received, false
      otherwise."""

    # Inclusion of the script that provides
    # window.__telemetry_testHasReachedNetworkQuiescence()
    # is idempotent, it's run on every call because WebContents doesn't track
    # page loads and we need to execute anew for every newly loaded page.
    has_reached_quiescence = (
        self.EvaluateJavaScript(self._quiescence_js +
            "window.__telemetry_testHasReachedNetworkQuiescence()"))
    return has_reached_quiescence

  def ExecuteJavaScript(self, expr, timeout=DEFAULT_WEB_CONTENTS_TIMEOUT):
    """Executes expr in JavaScript. Does not return the result.

    If the expression failed to evaluate, EvaluateException will be raised.
    """
    self._inspector_backend.ExecuteJavaScript(expr, timeout)

  def EvaluateJavaScript(self, expr, timeout=DEFAULT_WEB_CONTENTS_TIMEOUT):
    """Evalutes expr in JavaScript and returns the JSONized result.

    Consider using ExecuteJavaScript for cases where the result of the
    expression is not needed.

    If evaluation throws in JavaScript, a Python EvaluateException will
    be raised.

    If the result of the evaluation cannot be JSONized, then an
    EvaluationException will be raised.
    """
    return self._inspector_backend.EvaluateJavaScript(expr, timeout)

  @property
  def message_output_stream(self):
    return self._inspector_backend.message_output_stream

  @message_output_stream.setter
  def message_output_stream(self, stream):
    self._inspector_backend.message_output_stream = stream

  @property
  def timeline_model(self):
    return self._inspector_backend.timeline_model

  def StartTimelineRecording(self, options=None):
    self._inspector_backend.StartTimelineRecording(options)

  @property
  def is_timeline_recording_running(self):
    return self._inspector_backend.is_timeline_recording_running

  def StopTimelineRecording(self):
    self._inspector_backend.StopTimelineRecording()

  def TakeJSHeapSnapshot(self, timeout=120):
    return self._inspector_backend.TakeJSHeapSnapshot(timeout)
