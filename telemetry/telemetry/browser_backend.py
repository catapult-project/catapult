# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib2
import httplib
import socket
import json
import re
import sys

from telemetry import browser_gone_exception
from telemetry import options_for_unittests
from telemetry import tab_list_backend
from telemetry import tracing_backend
from telemetry import user_agent
from telemetry import util
from telemetry import wpr_modes
from telemetry import wpr_server

class BrowserBackend(object):
  """A base class for browser backends. Provides basic functionality
  once a remote-debugger port has been established."""

  WEBPAGEREPLAY_HOST = '127.0.0.1'
  WEBPAGEREPLAY_HTTP_PORT = 8080
  WEBPAGEREPLAY_HTTPS_PORT = 8413

  def __init__(self, is_content_shell, options):
    self.browser_type = options.browser_type
    self.is_content_shell = is_content_shell
    self.options = options
    self._browser = None
    self._port = None

    self._inspector_protocol_version = 0
    self._chrome_branch_number = 0
    self._webkit_base_revision = 0
    self._tracing_backend = None

    if options.dont_override_profile and not options_for_unittests.AreSet():
      sys.stderr.write('Warning: Not overriding profile. This can cause '
                       'unexpected effects due to profile-specific settings, '
                       'such as about:flags settings, cookies, and '
                       'extensions.\n')
    self._tab_list_backend = tab_list_backend.TabListBackend(self)

  def SetBrowser(self, browser):
    self._browser = browser
    self._tab_list_backend.Init()

  @property
  def browser(self):
    return self._browser

  @property
  def tab_list_backend(self):
    return self._tab_list_backend

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
  def chrome_branch_number(self):
    return self._chrome_branch_number

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
    self._tracing_backend.EndTracing()

  def GetTrace(self):
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
