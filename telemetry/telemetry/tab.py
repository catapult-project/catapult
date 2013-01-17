# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEFAULT_TAB_TIMEOUT = 60

class Tab(object):
  """Represents a tab in the browser

  The important parts of the Tab object are in the runtime and page objects.
  E.g.:
      # Navigates the tab to a given url.
      tab.Navigate('http://www.google.com/')

      # Evaluates 1+1 in the tab's JavaScript context.
      tab.Evaluate('1+1')
  """
  def __init__(self, backend):
    self._backend = backend

  def Disconnect(self):
    self._backend.Disconnect()

  @property
  def browser(self):
    """The browser in which this tab resides."""
    return self._backend.browser

  @property
  def url(self):
    return self._backend.url

  def Activate(self):
    """Brings this tab to the foreground asynchronously.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control.

    Please note: this is asynchronous. There is a delay between this call
    and the page's documentVisibilityState becoming 'visible', and yet more
    delay until the actual tab is visible to the user. None of these delays
    are included in this call."""
    self._backend.Activate()

  def Close(self):
    """Closes this tab.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control."""
    self._backend.Close()

  def WaitForDocumentReadyStateToBeComplete(self, timeout=DEFAULT_TAB_TIMEOUT):
    self._backend.WaitForDocumentReadyStateToBeComplete(timeout)

  def WaitForDocumentReadyStateToBeInteractiveOrBetter(
      self, timeout=DEFAULT_TAB_TIMEOUT):
    self._backend.WaitForDocumentReadyStateToBeInteractiveOrBetter(timeout)

  @property
  def screenshot_supported(self):
    """True if the browser instance is capable of capturing screenshots"""
    return self._backend.screenshot_supported

  def Screenshot(self, timeout=DEFAULT_TAB_TIMEOUT):
    """Capture a screenshot of the window for rendering validation"""
    return self._backend.Screenshot(timeout)

  @property
  def message_output_stream(self):
    return self._backend.message_output_stream

  @message_output_stream.setter
  def message_output_stream(self, stream):
    self._backend.message_output_stream = stream

  def PerformActionAndWaitForNavigate(
      self, action_function, timeout=DEFAULT_TAB_TIMEOUT):
    """Executes action_function, and waits for the navigation to complete.

    action_function must be a Python function that results in a navigation.
    This function returns when the navigation is complete or when
    the timeout has been exceeded.
    """
    self._backend.PerformActionAndWaitForNavigate(action_function, timeout)

  def Navigate(self, url, timeout=DEFAULT_TAB_TIMEOUT):
    """Navigates to url."""
    self._backend.Navigate(url, timeout)

  def GetCookieByName(self, name, timeout=DEFAULT_TAB_TIMEOUT):
    """Returns the value of the cookie by the given |name|."""
    return self._backend.GetCookieByName(name, timeout)

  def ExecuteJavaScript(self, expr, timeout=DEFAULT_TAB_TIMEOUT):
    """Executes expr in JavaScript. Does not return the result.

    If the expression failed to evaluate, EvaluateException will be raised.
    """
    self._backend.ExecuteJavaScript(expr, timeout)

  def EvaluateJavaScript(self, expr, timeout=DEFAULT_TAB_TIMEOUT):
    """Evalutes expr in JavaScript and returns the JSONized result.

    Consider using ExecuteJavaScript for cases where the result of the
    expression is not needed.

    If evaluation throws in JavaScript, a Python EvaluateException will
    be raised.

    If the result of the evaluation cannot be JSONized, then an
    EvaluationException will be raised.
    """
    return self._backend.EvaluateJavaScript(expr, timeout)

  @property
  def timeline_model(self):
    return self._backend.timeline_model

  def StartTimelineRecording(self):
    self._backend.StartTimelineRecording()

  def StopTimelineRecording(self):
    self._backend.StopTimelineRecording()
