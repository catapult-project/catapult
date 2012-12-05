# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import urllib2
import httplib
import socket
import json
import re

from telemetry import browser_gone_exception
from telemetry import inspector_backend
from telemetry import tab
from telemetry import user_agent
from telemetry import util
from telemetry import wpr_modes
from telemetry import wpr_server


class BrowserConnectionGoneException(
    browser_gone_exception.BrowserGoneException):
  pass


class BrowserBackend(object):
  """A base class for browser backends. Provides basic functionality
  once a remote-debugger port has been established."""
  def __init__(self, is_content_shell, options):
    self.browser_type = options.browser_type
    self.is_content_shell = is_content_shell
    self.options = options
    self._port = None

    self._inspector_protocol_version = 0
    self._chrome_branch_number = 0
    self._webkit_base_revision = 0

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.options.extra_browser_args)
    args.append('--disable-background-networking')
    args.append('--metrics-recording-only')
    args.append('--no-first-run')
    if self.options.wpr_mode != wpr_modes.WPR_OFF:
      args.extend(wpr_server.CHROME_FLAGS)
    args.extend(user_agent.GetChromeUserAgentArgumentFromType(
        self.options.browser_user_agent_type))
    return args

  @property
  def wpr_mode(self):
    return self.options.wpr_mode

  def _WaitForBrowserToComeUp(self):
    def IsBrowserUp():
      try:
        self._ListTabs()
      except BrowserConnectionGoneException:
        return False
      else:
        return True
    try:
      util.WaitFor(IsBrowserUp, timeout=30)
    except util.TimeoutException:
      raise browser_gone_exception.BrowserGoneException()

  def _PostBrowserStartupInitialization(self):
    # Detect version information.
    data = self._Request('version')
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

  def _Request(self, path, timeout=None):
    url = 'http://localhost:%i/json/%s' % (self._port, path)
    req = urllib2.urlopen(url, timeout=timeout)
    return req.read()

  def _ListTabs(self, timeout=None):
    try:
      data = self._Request('', timeout=timeout)
      all_contexts = json.loads(data)
      tabs = [ctx for ctx in all_contexts
              if not ctx['url'].startswith('chrome-extension://')]
      # FIXME(dtu): The remote debugger protocol returns in order of most
      # recently created tab first. In order to convert it to the UI tab
      # order, we just reverse the list, which assumes we can't move tabs.
      # We should guarantee that the remote debugger returns in UI tab order.
      tabs.reverse()
      return tabs
    except (socket.error, httplib.BadStatusLine, urllib2.URLError):
      if not self.IsBrowserRunning():
        raise browser_gone_exception.BrowserGoneException()
      raise BrowserConnectionGoneException()

  def NewTab(self, timeout=None):
    data = self._Request('new', timeout=timeout)
    new_tab = json.loads(data)
    return new_tab

  def CloseTab(self, index, timeout=None):
    assert self.num_tabs > 1, 'Closing the last tab not supported.'
    target_tab = self._ListTabs()[index]
    tab_id = target_tab['webSocketDebuggerUrl'].split('/')[-1]
    target_num_tabs = self.num_tabs - 1

    self._Request('close/%s' % tab_id, timeout=timeout)

    util.WaitFor(lambda: self.num_tabs == target_num_tabs, timeout=5)

  @property
  def num_tabs(self):
    return len(self._ListTabs())

  def GetNthTabUrl(self, index):
    return self._ListTabs()[index]['url']

  def ConnectToNthTab(self, browser, index):
    ib = inspector_backend.InspectorBackend(self, self._ListTabs()[index])
    return tab.Tab(browser, ib)

  def DoesDebuggerUrlExist(self, url):
    matches = [t for t in self._ListTabs()
               if 'webSocketDebuggerUrl' in t and\
               t['webSocketDebuggerUrl'] == url]
    return len(matches) >= 1

  def CreateForwarder(self, host_port):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()
