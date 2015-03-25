# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.backends.chrome_inspector import inspector_backend_list
from telemetry.core import exceptions
from telemetry.core import tab
from telemetry.core import util


class TabUnexpectedResponseException(exceptions.Error):
  pass


class TabListBackend(inspector_backend_list.InspectorBackendList):
  """A dynamic sequence of tab.Tabs in UI order."""

  def __init__(self, browser_backend):
    super(TabListBackend, self).__init__(browser_backend)

  def New(self, timeout):
    """Makes a new tab.

    Raises:
      devtools_http.DevToolsClientConnectionError
    """
    assert self._browser_backend.supports_tab_control
    self._browser_backend.devtools_client.CreateNewTab(timeout)
    return self[-1]

  def CloseTab(self, tab_id, timeout=None):
    """Closes the tab with the given debugger_url.

    Raises:
      devtools_http.DevToolsClientConnectionError
      devtools_client_backend.TabNotFoundError
      TabUnexpectedResponseException
      exceptions.TimeoutException
    """
    assert self._browser_backend.supports_tab_control
    # TODO(dtu): crbug.com/160946, allow closing the last tab on some platforms.
    # For now, just create a new tab before closing the last tab.
    if len(self) <= 1:
      self.New(timeout)

    response = self._browser_backend.devtools_client.CloseTab(tab_id, timeout)

    if response != 'Target is closing':
      raise TabUnexpectedResponseException('Received response: %s' % response)

    util.WaitFor(lambda: tab_id not in self, timeout=5)

  def ActivateTab(self, tab_id, timeout=None):
    """Activates the tab with the given debugger_url.

    Raises:
      devtools_http.DevToolsClientConnectionError
      devtools_client_backend.TabNotFoundError
      TabUnexpectedResponseException
    """
    assert self._browser_backend.supports_tab_control

    response = self._browser_backend.devtools_client.ActivateTab(tab_id,
                                                                 timeout)

    if response != 'Target activated':
      raise TabUnexpectedResponseException('Received response: %s' % response)

  def Get(self, index, ret):
    """Returns self[index] if it exists, or ret if index is out of bounds."""
    if len(self) <= index:
      return ret
    return self[index]

  def ShouldIncludeContext(self, context):
    if 'type' in context:
      return context['type'] == 'page'
    # TODO: For compatibility with Chrome before r177683.
    # This check is not completely correct, see crbug.com/190592.
    return not context['url'].startswith('chrome-extension://')

  def CreateWrapper(self, inspector_backend):
    return tab.Tab(inspector_backend, self, self._browser_backend.browser)

  def _HandleDevToolsConnectionError(self, error):
    if not self._browser_backend.IsAppRunning():
      error.AddDebuggingMessage('The browser is not running. It probably '
                                'crashed.')
    elif not self._browser_backend.HasBrowserFinishedLaunching():
      error.AddDebuggingMessage('The browser exists but cannot be reached.')
    else:
      error.AddDebuggingMessage('The browser exists and can be reached. '
                                'The devtools target probably crashed.')
