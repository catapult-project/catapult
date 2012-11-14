# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import inspector_console
from telemetry import inspector_page
from telemetry import inspector_runtime
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
  def __init__(self, browser, inspector_backend):
    self._browser = browser
    self._inspector_backend = inspector_backend
    self._page = inspector_page.InspectorPage(self._inspector_backend, self)
    self._runtime = inspector_runtime.InspectorRuntime(
        self._inspector_backend, self)
    self._console = inspector_console.InspectorConsole(
        self._inspector_backend, self)

  def __del__(self):
    self.Close()

  def Close(self):
    self._console = None
    self._runtime = None
    self._page = None
    if self._inspector_backend:
      self._inspector_backend.Close()
      self._inspector_backend = None
    self._browser = None

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  @property
  def browser(self):
    """The browser in which this tab resides."""
    return self._browser

  @property
  def page(self):
    """Methods for interacting with the current page."""
    return self._page

  @property
  def runtime(self):
    """Methods for interacting with the page's javascript runtime."""
    return self._runtime

  @property
  def console(self):
    """Methods for interacting with the page's console objec."""
    return self._console

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
