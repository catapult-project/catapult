# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib2

from telemetry.core import tab
from telemetry.core import util
from telemetry.core.backends.chrome import inspector_backend_list


class TabListBackend(inspector_backend_list.InspectorBackendList):
  """A dynamic sequence of tab.Tabs in UI order."""

  def __init__(self, browser_backend):
    super(TabListBackend, self).__init__(browser_backend,
                                         backend_wrapper=tab.Tab)

  def New(self, timeout):
    assert self._browser_backend.supports_tab_control
    self._browser_backend.Request('new', timeout=timeout)
    return self[-1]

  def CloseTab(self, debugger_url, timeout=None):
    assert self._browser_backend.supports_tab_control
    tab_id = inspector_backend_list.DebuggerUrlToId(debugger_url)
    # TODO(dtu): crbug.com/160946, allow closing the last tab on some platforms.
    # For now, just create a new tab before closing the last tab.
    if len(self) <= 1:
      self.New(timeout)
    try:
      response = self._browser_backend.Request('close/%s' % tab_id,
                                               timeout=timeout,
                                               throw_network_exception=True)
    except urllib2.HTTPError:
      raise Exception('Unable to close tab, tab id not found: %s' % tab_id)
    assert response == 'Target is closing'
    util.WaitFor(lambda: tab_id not in self, timeout=5)

  def ActivateTab(self, debugger_url, timeout=None):
    assert self._browser_backend.supports_tab_control
    tab_id = inspector_backend_list.DebuggerUrlToId(debugger_url)
    assert tab_id in self
    try:
      response = self._browser_backend.Request('activate/%s' % tab_id,
                                               timeout=timeout,
                                               throw_network_exception=True)
    except urllib2.HTTPError:
      raise Exception('Unable to activate tab, tab id not found: %s' % tab_id)
    assert response == 'Target activated'

  def GetTabUrl(self, debugger_url):
    tab_id = inspector_backend_list.DebuggerUrlToId(debugger_url)
    tab_info = self.GetContextInfo(tab_id)
    assert tab_info is not None
    return tab_info['url']

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
