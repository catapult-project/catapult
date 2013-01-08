# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib2
import httplib
import socket
import json
import re
import weakref

from telemetry import browser_gone_exception
from telemetry import tab
from telemetry import tracing_backend
from telemetry import user_agent
from telemetry import util
from telemetry import wpr_modes
from telemetry import wpr_server


class BrowserConnectionGoneException(
    browser_gone_exception.BrowserGoneException):
  pass


class TabController(object):
  def __init__(self, browser, browser_backend):
    self._browser = browser
    self._browser_backend = browser_backend

    # Stores web socket debugger URLs in iteration order.
    self._tab_list = []
    # Maps debugger URLs to Tab objects.
    self._tab_dict = weakref.WeakValueDictionary()

    self._UpdateTabList()

  def New(self, timeout=None):
    self._browser_backend.Request('new', timeout=timeout)
    return self[-1]

  def DoesDebuggerUrlExist(self, url):
    self._UpdateTabList()
    return url in self._tab_list

  def CloseTab(self, debugger_url, timeout=None):
    # TODO(dtu): crbug.com/160946, allow closing the last tab on some platforms.
    # For now, just create a new tab before closing the last tab.
    if len(self) <= 1:
      self.New()

    tab_id = debugger_url.split('/')[-1]
    try:
      response = self._browser_backend.Request('close/%s' % tab_id,
                                               timeout=timeout)
    except urllib2.HTTPError:
      raise Exception('Unable to close tab, tab id not found: %s' % tab_id)
    assert response == 'Target is closing'

    util.WaitFor(lambda: not self._FindTabInfo(debugger_url), timeout=5)
    self._UpdateTabList()

  def ActivateTab(self, debugger_url, timeout=None):
    assert debugger_url in self._tab_dict
    tab_id = debugger_url.split('/')[-1]
    try:
      response = self._browser_backend.Request('activate/%s' % tab_id,
                                               timeout=timeout)
    except urllib2.HTTPError:
      raise Exception('Unable to activate tab, tab id not found: %s' % tab_id)
    assert response == 'Target activated'

  def GetTabUrl(self, debugger_url):
    tab_info = self._FindTabInfo(debugger_url)
    # TODO(hartmanng): crbug.com/166886 (uncomment the following assert and
    # remove the extra None check when _ListTabs is fixed):
    # assert tab_info is not None
    if tab_info is None:
      return None
    return tab_info['url']

  def __iter__(self):
    self._UpdateTabList()
    return self._tab_list.__iter__()

  def __len__(self):
    self._UpdateTabList()
    return len(self._tab_list)

  def __getitem__(self, index):
    self._UpdateTabList()
    # This dereference will propagate IndexErrors.
    debugger_url = self._tab_list[index]
    # Lazily get/create a Tab object.
    tab_object = self._tab_dict.get(debugger_url)
    if not tab_object:
      tab_object = tab.Tab(self._browser, self, debugger_url)
      self._tab_dict[debugger_url] = tab_object
    return tab_object

  def _ListTabs(self, timeout=None):
    try:
      data = self._browser_backend.Request('', timeout=timeout)
      all_contexts = json.loads(data)
      tabs = [ctx for ctx in all_contexts
              if not ctx['url'].startswith('chrome-extension://')]
      return tabs
    except (socket.error, httplib.BadStatusLine, urllib2.URLError):
      if not self._browser_backend.IsBrowserRunning():
        raise browser_gone_exception.BrowserGoneException()
      raise BrowserConnectionGoneException()

  def _UpdateTabList(self):
    def GetDebuggerUrl(tab_info):
      if 'webSocketDebuggerUrl' not in tab_info:
        return None
      return tab_info['webSocketDebuggerUrl']
    new_tab_list = map(GetDebuggerUrl, self._ListTabs())
    self._tab_list = [t for t in self._tab_list if t in new_tab_list]
    self._tab_list += [t for t in new_tab_list if t not in self._tab_list]

  def _FindTabInfo(self, debugger_url):
    for tab_info in self._ListTabs():
      if tab_info.get('webSocketDebuggerUrl') == debugger_url:
        return tab_info
    return None


class BrowserBackend(object):
  """A base class for browser backends. Provides basic functionality
  once a remote-debugger port has been established."""

  WEBPAGEREPLAY_HOST = '127.0.0.1'
  WEBPAGEREPLAY_HTTP_PORT = 8080
  WEBPAGEREPLAY_HTTPS_PORT = 8413

  def __init__(self, is_content_shell, options):
    self.tabs = None
    self.browser_type = options.browser_type
    self.is_content_shell = is_content_shell
    self.options = options
    self._port = None

    self._inspector_protocol_version = 0
    self._chrome_branch_number = 0
    self._webkit_base_revision = 0
    self._tracing_backend = None

  def SetBrowser(self, browser):
    self.tabs = TabController(browser, self)

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.options.extra_browser_args)
    args.append('--disable-background-networking')
    args.append('--metrics-recording-only')
    args.append('--no-first-run')
    if self.options.wpr_mode != wpr_modes.WPR_OFF:
      args.extend(wpr_server.GetChromeFlags(self.WEBPAGEREPLAY_HOST,
                                            self.WEBPAGEREPLAY_HTTP_PORT,
                                            self.WEBPAGEREPLAY_HTTPS_PORT))
    args.extend(user_agent.GetChromeUserAgentArgumentFromType(
        self.options.browser_user_agent_type))
    return args

  @property
  def wpr_mode(self):
    return self.options.wpr_mode

  def _WaitForBrowserToComeUp(self, timeout=None):
    def IsBrowserUp():
      try:
        self.Request('', timeout=timeout)
      except (socket.error, httplib.BadStatusLine, urllib2.URLError):
        return False
      else:
        return True
    try:
      util.WaitFor(IsBrowserUp, timeout=30)
    except util.TimeoutException:
      raise browser_gone_exception.BrowserGoneException()

  def _PostBrowserStartupInitialization(self):
    # Detect version information.
    data = self.Request('version')
    resp = json.loads(data)
    if 'Protocol-Version' in resp:
      self._inspector_protocol_version = resp['Protocol-Version']
      mU = re.search('Chrome/\d+\.\d+\.(\d+)\.\d+ Safari', resp['User-Agent'])
      mW = re.search('\((trunk)?\@(\d+)\)', resp['WebKit-Version'])
      if mU:
        self._chrome_branch_number = int(mU.group(1))
      if mW:
        self._webkit_base_revision = int(mW.group(2))
      return

    # Detection has failed: assume 18.0.1025.168 ~= Chrome Android.
    self._inspector_protocol_version = 1.0
    self._chrome_branch_number = 1025
    self._webkit_base_revision = 106313

  def Request(self, path, timeout=None):
    url = 'http://localhost:%i/json' % self._port
    if path:
      url += '/' + path
    req = urllib2.urlopen(url, timeout=timeout)
    return req.read()

  @property
  def supports_tab_control(self):
    return self._chrome_branch_number >= 1303

  @property
  def supports_tracing(self):
    return True

  def StartTracing(self):
    if self._tracing_backend is None:
      self._tracing_backend = tracing_backend.TracingBackend(self._port)
    self._tracing_backend.BeginTracing()

  def StopTracing(self):
    self._tracing_backend.EndTracingAsync()

  def GetTrace(self):
    def IsTracingRunning(self):
      return not self._tracing_backend.HasCompleted()
    util.WaitFor(lambda: not IsTracingRunning(self), 10)
    return self._tracing_backend.GetTraceAndReset()

  def Close(self):
    if self._tracing_backend:
      self._tracing_backend.Close()
      self._tracing_backend = None

  def CreateForwarder(self, *port_pairs):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()

  def GetStandardOutput(self):
    raise NotImplementedError()
