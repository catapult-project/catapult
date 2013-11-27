# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json
import logging
import pprint
import re
import socket
import sys
import urllib2

from telemetry.core import exceptions
from telemetry.core import user_agent
from telemetry.core import util
from telemetry.core import web_contents
from telemetry.core import wpr_modes
from telemetry.core import wpr_server
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import extension_dict_backend
from telemetry.core.backends.chrome import misc_web_contents_backend
from telemetry.core.backends.chrome import system_info_backend
from telemetry.core.backends.chrome import tab_list_backend
from telemetry.core.backends.chrome import tracing_backend
from telemetry.unittest import options_for_unittests

class ChromeBrowserBackend(browser_backend.BrowserBackend):
  """An abstract class for chrome browser backends. Provides basic functionality
  once a remote-debugger port has been established."""
  # It is OK to have abstract methods. pylint: disable=W0223

  def __init__(self, is_content_shell, supports_extensions, browser_options,
               output_profile_path, extensions_to_load):
    super(ChromeBrowserBackend, self).__init__(
        is_content_shell=is_content_shell,
        supports_extensions=supports_extensions,
        browser_options=browser_options,
        tab_list_backend=tab_list_backend.TabListBackend)
    self._port = None

    self._inspector_protocol_version = 0
    self._chrome_branch_number = None
    self._tracing_backend = None
    self._system_info_backend = None

    self._output_profile_path = output_profile_path
    self._extensions_to_load = extensions_to_load

    if browser_options.netsim:
      self.wpr_http_port_pair = util.PortPair(80, 80)
      self.wpr_https_port_pair = util.PortPair(443, 443)
    else:
      self.wpr_http_port_pair = util.PortPair(0, 0)
      self.wpr_https_port_pair = util.PortPair(0, 0)

    if (self.browser_options.dont_override_profile and
        not options_for_unittests.AreSet()):
      sys.stderr.write('Warning: Not overriding profile. This can cause '
                       'unexpected effects due to profile-specific settings, '
                       'such as about:flags settings, cookies, and '
                       'extensions.\n')
    self._misc_web_contents_backend = (
        misc_web_contents_backend.MiscWebContentsBackend(self))
    self._extension_dict_backend = None
    if supports_extensions:
      self._extension_dict_backend = (
          extension_dict_backend.ExtensionDictBackend(self))

  def AddReplayServerOptions(self, extra_wpr_args):
    if self.browser_options.netsim:
      extra_wpr_args.append('--net=%s' % self.browser_options.netsim)
    else:
      extra_wpr_args.append('--no-dns_forwarding')

  @property
  def misc_web_contents_backend(self):
    """Access to chrome://oobe/login page which is neither a tab nor an
    extension."""
    return self._misc_web_contents_backend

  @property
  def extension_dict_backend(self):
    return self._extension_dict_backend

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.browser_options.extra_browser_args)
    args.append('--disable-background-networking')
    args.append('--metrics-recording-only')
    args.append('--no-first-run')
    args.append('--no-default-browser-check')
    args.append('--no-proxy-server')
    if self.browser_options.netsim:
      args.append('--ignore-certificate-errors')
    elif self.browser_options.wpr_mode != wpr_modes.WPR_OFF:
      args.extend(wpr_server.GetChromeFlags(
          self.WEBPAGEREPLAY_HOST,
          self.wpr_http_port_pair.remote_port,
          self.wpr_https_port_pair.remote_port))
    args.extend(user_agent.GetChromeUserAgentArgumentFromType(
        self.browser_options.browser_user_agent_type))

    extensions = [extension.local_path
                  for extension in self._extensions_to_load
                  if not extension.is_component]
    extension_str = ','.join(extensions)
    if len(extensions) > 0:
      args.append('--load-extension=%s' % extension_str)

    component_extensions = [extension.local_path
                            for extension in self._extensions_to_load
                            if extension.is_component]
    component_extension_str = ','.join(component_extensions)
    if len(component_extensions) > 0:
      args.append('--load-component-extension=%s' % component_extension_str)

    if self.browser_options.no_proxy_server:
      args.append('--no-proxy-server')

    if self.browser_options.disable_component_extensions_with_background_pages:
      args.append('--disable-component-extensions-with-background-pages')

    return args

  def _WaitForBrowserToComeUp(self, wait_for_extensions=True, timeout=None):
    def IsBrowserUp():
      try:
        self.Request('', timeout=timeout)
      except (exceptions.BrowserGoneException,
              exceptions.BrowserConnectionGoneException):
        return False
      else:
        return True
    try:
      util.WaitFor(IsBrowserUp, timeout=30)
    except util.TimeoutException:
      raise exceptions.BrowserGoneException(self.GetStackTrace())

    def AllExtensionsLoaded():
      # Extension pages are loaded from an about:blank page,
      # so we need to check that the document URL is the extension
      # page in addition to the ready state.
      extension_ready_js = """
          document.URL.lastIndexOf('chrome-extension://%s/', 0) == 0 &&
          (document.readyState == 'complete' ||
           document.readyState == 'interactive')
      """
      for e in self._extensions_to_load:
        if not e.extension_id in self._extension_dict_backend:
          return False
        extension_object = self._extension_dict_backend[e.extension_id]
        try:
          res = extension_object.EvaluateJavaScript(
              extension_ready_js % e.extension_id)
        except exceptions.EvaluateException:
          # If the inspected page is not ready, we will get an error
          # when we evaluate a JS expression, but we can just keep polling
          # until the page is ready (crbug.com/251913).
          res = None

        # TODO(tengs): We don't have full support for getting the Chrome
        # version before launch, so for now we use a generic workaround to
        # check for an extension binding bug in old versions of Chrome.
        # See crbug.com/263162 for details.
        if res and extension_object.EvaluateJavaScript(
            'chrome.runtime == null'):
          extension_object.Reload()
        if not res:
          return False
      return True
    if wait_for_extensions and self._supports_extensions:
      try:
        util.WaitFor(AllExtensionsLoaded, timeout=60)
      except util.TimeoutException:
        logging.error('ExtensionsToLoad: ' +
            repr([e.extension_id for e in self._extensions_to_load]))
        logging.error('Extension list: ' +
            pprint.pformat(self._extension_dict_backend.GetExtensionInfoList(),
                           indent=4))
        raise


  def _PostBrowserStartupInitialization(self):
    # Detect version information.
    data = self.Request('version')
    resp = json.loads(data)
    if 'Protocol-Version' in resp:
      self._inspector_protocol_version = resp['Protocol-Version']

      if self._chrome_branch_number:
        return

      if 'Browser' in resp:
        branch_number_match = re.search('Chrome/\d+\.\d+\.(\d+)\.\d+',
                                        resp['Browser'])
      else:
        branch_number_match = re.search(
            'Chrome/\d+\.\d+\.(\d+)\.\d+ (Mobile )?Safari',
            resp['User-Agent'])

      if branch_number_match:
        self._chrome_branch_number = int(branch_number_match.group(1))

      if not self._chrome_branch_number:
        # Content Shell returns '' for Browser, WebViewShell returns '0'.
        # For now we have to fall-back and assume branch 1025.
        self._chrome_branch_number = 1025
      return

    # Detection has failed: assume 18.0.1025.168 ~= Chrome Android.
    self._inspector_protocol_version = 1.0
    self._chrome_branch_number = 1025

  def Request(self, path, timeout=None, throw_network_exception=False):
    url = 'http://127.0.0.1:%i/json' % self._port
    if path:
      url += '/' + path
    try:
      proxy_handler = urllib2.ProxyHandler({})  # Bypass any system proxy.
      opener = urllib2.build_opener(proxy_handler)
      req = opener.open(url, timeout=timeout)
      return req.read()
    except (socket.error, httplib.BadStatusLine, urllib2.URLError) as e:
      if throw_network_exception:
        raise e
      if not self.IsBrowserRunning():
        raise exceptions.BrowserGoneException(e)
      raise exceptions.BrowserConnectionGoneException(e)

  @property
  def browser_directory(self):
    raise NotImplementedError()

  @property
  def profile_directory(self):
    raise NotImplementedError()

  @property
  def chrome_branch_number(self):
    assert self._chrome_branch_number
    return self._chrome_branch_number

  @property
  def supports_tab_control(self):
    return self.chrome_branch_number >= 1303

  @property
  def supports_tracing(self):
    return self.is_content_shell or self.chrome_branch_number >= 1385

  def StartTracing(self, custom_categories=None,
                   timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    """ custom_categories is an optional string containing a list of
    comma separated categories that will be traced instead of the
    default category set.  Example: use
    "webkit,cc,disabled-by-default-cc.debug" to trace only those three
    event categories.
    """
    if self._tracing_backend is None:
      self._tracing_backend = tracing_backend.TracingBackend(self._port)
    return self._tracing_backend.StartTracing(custom_categories, timeout)

  def StopTracing(self):
    """ Stops tracing and returns the result as TraceResult object. """
    for (i, debugger_url) in enumerate(self._browser.tabs):
      tab = self.tab_list_backend.Get(i, None)
      if tab:
        success = tab.EvaluateJavaScript(
            "console.time('" + debugger_url + "');" +
            "console.timeEnd('" + debugger_url + "');" +
            "console.time.toString().indexOf('[native code]') != -1;")
        if not success:
          raise Exception('Page stomped on console.time')
        self._tracing_backend.AddTabToMarkerMapping(tab, debugger_url)
    return self._tracing_backend.StopTracing()

  def GetProcessName(self, cmd_line):
    """Returns a user-friendly name for the process of the given |cmd_line|."""
    if not cmd_line:
      # TODO(tonyg): Eventually we should make all of these known and add an
      # assertion.
      return 'unknown'
    if 'nacl_helper_bootstrap' in cmd_line:
      return 'nacl_helper_bootstrap'
    if ':sandboxed_process' in cmd_line:
      return 'renderer'
    m = re.match(r'.* --type=([^\s]*) .*', cmd_line)
    if not m:
      return 'browser'
    return m.group(1)

  def Close(self):
    if self._tracing_backend:
      self._tracing_backend.Close()
      self._tracing_backend = None

  @property
  def supports_system_info(self):
    return self.GetSystemInfo() != None

  def GetSystemInfo(self):
    if self._system_info_backend is None:
      self._system_info_backend = system_info_backend.SystemInfoBackend(
          self._port)
    return self._system_info_backend.GetSystemInfo()

  def _SetBranchNumber(self, version):
    assert version
    self._chrome_branch_number = re.search(r'\d+\.\d+\.(\d+)\.\d+',
                                           version).group(1)
