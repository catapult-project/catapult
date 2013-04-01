# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib2
import httplib
import socket
import json
import re
import sys

from telemetry.core import util
from telemetry.core import exceptions
from telemetry.core import user_agent
from telemetry.core import wpr_modes
from telemetry.core import wpr_server
from telemetry.core.chrome import extension_dict_backend
from telemetry.core.chrome import tab_list_backend
from telemetry.core.chrome import tracing_backend
from telemetry.test import options_for_unittests

class ExtensionsNotSupportedException(Exception):
  pass

class BrowserBackend(object):
  """A base class for browser backends. Provides basic functionality
  once a remote-debugger port has been established."""

  WEBPAGEREPLAY_HOST = '127.0.0.1'

  def __init__(self, is_content_shell, supports_extensions, options):
    self.browser_type = options.browser_type
    self.is_content_shell = is_content_shell
    self._supports_extensions = supports_extensions
    self.options = options
    self._browser = None
    self._port = None

    self._inspector_protocol_version = 0
    self._chrome_branch_number = 0
    self._webkit_base_revision = 0
    self._tracing_backend = None

    self.webpagereplay_local_http_port = util.GetAvailableLocalPort()
    self.webpagereplay_local_https_port = util.GetAvailableLocalPort()
    self.webpagereplay_remote_http_port = self.webpagereplay_local_http_port
    self.webpagereplay_remote_https_port = self.webpagereplay_local_https_port

    if options.dont_override_profile and not options_for_unittests.AreSet():
      sys.stderr.write('Warning: Not overriding profile. This can cause '
                       'unexpected effects due to profile-specific settings, '
                       'such as about:flags settings, cookies, and '
                       'extensions.\n')
    self._tab_list_backend = tab_list_backend.TabListBackend(self)
    self._extension_dict_backend = None
    if supports_extensions:
      self._extension_dict_backend = \
          extension_dict_backend.ExtensionDictBackend(self)

  def SetBrowser(self, browser):
    self._browser = browser
    self._tab_list_backend.Init()

  @property
  def browser(self):
    return self._browser

  @property
  def supports_extensions(self):
    """True if this browser backend supports extensions."""
    return self._supports_extensions

  @property
  def tab_list_backend(self):
    return self._tab_list_backend

  @property
  def extension_dict_backend(self):
    return self._extension_dict_backend

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.options.extra_browser_args)
    args.append('--disable-background-networking')
    args.append('--metrics-recording-only')
    args.append('--no-first-run')
    if self.options.wpr_mode != wpr_modes.WPR_OFF:
      args.extend(wpr_server.GetChromeFlags(
          self.WEBPAGEREPLAY_HOST,
          self.webpagereplay_remote_http_port,
          self.webpagereplay_remote_https_port))
    args.extend(user_agent.GetChromeUserAgentArgumentFromType(
        self.options.browser_user_agent_type))

    extensions = [extension.local_path for extension in
                  self.options.extensions_to_load if not extension.is_component]
    extension_str = ','.join(extensions)
    if len(extensions) > 0:
      args.append('--load-extension=%s' % extension_str)

    component_extensions = [extension.local_path for extension in
                  self.options.extensions_to_load if extension.is_component]
    component_extension_str = ','.join(component_extensions)
    if len(component_extensions) > 0:
      args.append('--load-component-extension=%s' % component_extension_str)
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
      raise exceptions.BrowserGoneException()

    def AllExtensionsLoaded():
      for e in self.options.extensions_to_load:
        if not e.extension_id in self._extension_dict_backend:
          return False
        extension_object = self._extension_dict_backend[e.extension_id]
        extension_object.WaitForDocumentReadyStateToBeInteractiveOrBetter()
      return True
    if self._supports_extensions:
      util.WaitFor(AllExtensionsLoaded, timeout=30)

  def _PostBrowserStartupInitialization(self):
    # Detect version information.
    data = self.Request('version')
    resp = json.loads(data)
    if 'Protocol-Version' in resp:
      self._inspector_protocol_version = resp['Protocol-Version']
      if 'Browser' in resp:
        branch_number_match = re.search('Chrome/\d+\.\d+\.(\d+)\.\d+',
                                        resp['Browser'])
      else:
        branch_number_match = re.search(
            'Chrome/\d+\.\d+\.(\d+)\.\d+ (Mobile )?Safari',
            resp['User-Agent'])
      webkit_version_match = re.search('\((trunk)?\@(\d+)\)',
                                       resp['WebKit-Version'])

      if branch_number_match:
        self._chrome_branch_number = int(branch_number_match.group(1))
      else:
        # Content Shell returns '' for Browser, for now we have to
        # fall-back and assume branch 1025.
        self._chrome_branch_number = 1025

      if webkit_version_match:
        self._webkit_base_revision = int(webkit_version_match.group(2))
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
    return self.is_content_shell or self._chrome_branch_number >= 1385

  def StartTracing(self):
    if self._tracing_backend is None:
      self._tracing_backend = tracing_backend.TracingBackend(self._port)
    self._tracing_backend.BeginTracing()

  def StopTracing(self):
    self._tracing_backend.EndTracing()

  def GetTraceResultAndReset(self):
    return self._tracing_backend.GetTraceResultAndReset()

  def GetRemotePort(self, _):
    return util.GetAvailableLocalPort()

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

class DoNothingForwarder(object):
  def __init__(self, *port_pairs):
    self._host_port = port_pairs[0].local_port

  @property
  def url(self):
    assert self._host_port
    return 'http://127.0.0.1:%i' % self._host_port

  def Close(self):
    self._host_port = None
