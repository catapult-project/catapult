# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import inspector_backend
from telemetry import inspector_console
from telemetry import inspector_page
from telemetry import inspector_runtime
from telemetry import inspector_timeline
from telemetry import util

DEFAULT_TAB_TIMEOUT = 60

class Tab(object):
  """Represents a tab in the browser

  The important parts of the Tab object are in the runtime and page objects.
  E.g.:
      # Navigates the tab to a given url.
      tab.page.Navigate('http://www.google.com/')

      # Evaluates 1+1 in the tab's javascript context.
      tab.runtime.Evaluate('1+1')
  """
  def __init__(self, browser, tab_controller, debugger_url):
    self._browser = browser
    self._tab_controller = tab_controller
    self._debugger_url = debugger_url

    self._inspector_backend = None
    self._console = None
    self._page = None
    self._runtime = None
    self._timeline = None

  def __del__(self):
    self.Disconnect()

  def _Connect(self):
    if self._inspector_backend:
      return

    self._inspector_backend = inspector_backend.InspectorBackend(
        self._tab_controller, self._debugger_url)
    self._console = inspector_console.InspectorConsole(
        self._inspector_backend, self)
    self._page = inspector_page.InspectorPage(self._inspector_backend, self)
    self._runtime = inspector_runtime.InspectorRuntime(
        self._inspector_backend, self)
    self._timeline = inspector_timeline.InspectorTimeline(
        self._inspector_backend, self)

  def Disconnect(self):
    """Closes the connection to this tab."""
    self._console = None
    self._page = None
    self._runtime = None
    self._timeline = None
    if self._inspector_backend:
      self._inspector_backend.Close()
      self._inspector_backend = None
    self._browser = None

  def Close(self):
    """Closes this tab.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control."""
    self.Disconnect()
    self._tab_controller.CloseTab(self._debugger_url)

  def Activate(self):
    """Brings this tab to the foreground asynchronously.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control.

    Please note: this is asynchronous. There is a delay between this call
    and the page's documentVisibilityState becoming 'visible', and yet more
    delay until the actual tab is visible to the user. None of these delays
    are included in this call."""
    self._Connect()
    self._tab_controller.ActivateTab(self._debugger_url)

  @property
  def browser(self):
    """The browser in which this tab resides."""
    return self._browser

  @property
  def url(self):
    return self._tab_controller.GetTabUrl(self._debugger_url)

  @property
  def console(self):
    """Methods for interacting with the page's console object."""
    self._Connect()
    return self._console

  @property
  def page(self):
    """Methods for interacting with the current page."""
    self._Connect()
    return self._page

  @property
  def runtime(self):
    """Methods for interacting with the page's javascript runtime."""
    self._Connect()
    return self._runtime

  @property
  def timeline(self):
    """Methods for interacting with the inspector timeline."""
    self._Connect()
    return self._timeline

  def WaitForDocumentReadyStateToBeComplete(self, timeout=DEFAULT_TAB_TIMEOUT):
    util.WaitFor(
        lambda: self._runtime.Evaluate('document.readyState') == 'complete',
        timeout)

  def WaitForDocumentReadyStateToBeInteractiveOrBetter(
      self, timeout=DEFAULT_TAB_TIMEOUT):
    def IsReadyStateInteractiveOrBetter():
      rs = self._runtime.Evaluate('document.readyState')
      return rs == 'complete' or rs == 'interactive'
    util.WaitFor(IsReadyStateInteractiveOrBetter, timeout)

