# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import httplib
import json
import logging
import pprint
import re
import socket
import sys
import urllib2

from telemetry import decorators
from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import user_agent
from telemetry.core import util
from telemetry.core import web_contents
from telemetry.core import wpr_modes
from telemetry.core import wpr_server
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import extension_backend
from telemetry.core.backends.chrome import system_info_backend
from telemetry.core.backends.chrome import tab_list_backend
from telemetry.core.backends.chrome import tracing_backend
from telemetry.timeline import tracing_timeline_data
from telemetry.unittest import options_for_unittests


class ChromeBrowserBackend(browser_backend.BrowserBackend):
  """An abstract class for chrome browser backends. Provides basic functionality
  once a remote-debugger port has been established."""
  # It is OK to have abstract methods. pylint: disable=W0223

  def __init__(self, supports_tab_control, supports_extensions, browser_options,
               output_profile_path, extensions_to_load):
    super(ChromeBrowserBackend, self).__init__(
        supports_extensions=supports_extensions,
        browser_options=browser_options,
        tab_list_backend=tab_list_backend.TabListBackend)
    self._port = None

    self._supports_tab_control = supports_tab_control
    self._tracing_backend = None
    self._system_info_backend = None

    self._output_profile_path = output_profile_path
    self._extensions_to_load = extensions_to_load

    if browser_options.netsim:
      self.wpr_port_pairs = forwarders.PortPairs(
          http=forwarders.PortPair(80, 80),
          https=forwarders.PortPair(443, 443),
          dns=forwarders.PortPair(53, 53))
    else:
      self.wpr_port_pairs = forwarders.PortPairs(
          http=forwarders.PortPair(0, 0),
          https=forwarders.PortPair(0, 0),
          dns=None)

    if (self.browser_options.dont_override_profile and
        not options_for_unittests.AreSet()):
      sys.stderr.write('Warning: Not overriding profile. This can cause '
                       'unexpected effects due to profile-specific settings, '
                       'such as about:flags settings, cookies, and '
                       'extensions.\n')

  def AddReplayServerOptions(self, extra_wpr_args):
    if self.browser_options.netsim:
      extra_wpr_args.append('--net=%s' % self.browser_options.netsim)
    else:
      extra_wpr_args.append('--no-dns_forwarding')

  @property
  @decorators.Cache
  def extension_backend(self):
    if not self.supports_extensions:
      return None
    return extension_backend.ExtensionBackendDict(self)

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.browser_options.extra_browser_args)
    args.append('--disable-background-networking')
    args.append('--enable-net-benchmarking')
    args.append('--metrics-recording-only')
    args.append('--no-default-browser-check')
    args.append('--no-first-run')

    # Turn on GPU benchmarking extension for all runs. The only side effect of
    # the extension being on is that render stats are tracked. This is believed
    # to be effectively free. And, by doing so here, it avoids us having to
    # programmatically inspect a pageset's actions in order to determine if it
    # might eventually scroll.
    args.append('--enable-gpu-benchmarking')

    # Set --no-proxy-server to work around some XP issues unless
    # some other flag indicates a proxy is needed.
    if not '--enable-spdy-proxy-auth' in args:
      args.append('--no-proxy-server')

    if self.browser_options.netsim:
      args.append('--ignore-certificate-errors')
    elif self.browser_options.wpr_mode != wpr_modes.WPR_OFF:
      args.extend(wpr_server.GetChromeFlags(self.forwarder_factory.host_ip,
                                            self.wpr_port_pairs))
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

  def HasBrowserFinishedLaunching(self):
    try:
      self.Request('', timeout=.1)
    except (exceptions.BrowserGoneException,
            exceptions.BrowserConnectionGoneException):
      return False
    else:
      return True

  def _WaitForBrowserToComeUp(self, wait_for_extensions=True):
    try:
      util.WaitFor(self.HasBrowserFinishedLaunching, timeout=30)
    except (util.TimeoutException, exceptions.ProcessGoneException) as e:
      if not self.IsBrowserRunning():
        raise exceptions.BrowserGoneException(self.browser, e)
      raise exceptions.BrowserConnectionGoneException(self.browser, e)

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
        if not e.extension_id in self.extension_backend:
          return False
        for extension_object in self.extension_backend[e.extension_id]:
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
            pprint.pformat(self.extension_backend, indent=4))
        raise

  def ListInspectableContexts(self):
    return json.loads(self.Request(''))

  def Request(self, path, timeout=30, throw_network_exception=False):
    url = 'http://127.0.0.1:%i/json' % self._port
    if path:
      url += '/' + path
    try:
      proxy_handler = urllib2.ProxyHandler({})  # Bypass any system proxy.
      opener = urllib2.build_opener(proxy_handler)
      with contextlib.closing(opener.open(url, timeout=timeout)) as req:
        return req.read()
    except (socket.error, httplib.BadStatusLine, urllib2.URLError) as e:
      if throw_network_exception:
        raise e
      if not self.IsBrowserRunning():
        raise exceptions.BrowserGoneException(self.browser, e)
      raise exceptions.BrowserConnectionGoneException(self.browser, e)

  @property
  def browser_directory(self):
    raise NotImplementedError()

  @property
  def profile_directory(self):
    raise NotImplementedError()

  @property
  @decorators.Cache
  def chrome_branch_number(self):
    # Detect version information.
    data = self.Request('version')
    resp = json.loads(data)
    if 'Protocol-Version' in resp:
      if 'Browser' in resp:
        branch_number_match = re.search('Chrome/\d+\.\d+\.(\d+)\.\d+',
                                        resp['Browser'])
      else:
        branch_number_match = re.search(
            'Chrome/\d+\.\d+\.(\d+)\.\d+ (Mobile )?Safari',
            resp['User-Agent'])

      if branch_number_match:
        branch_number = int(branch_number_match.group(1))
        if branch_number:
          return branch_number

    # Branch number can't be determined, so fail any branch number checks.
    return 0

  @property
  def supports_tab_control(self):
    return self._supports_tab_control

  @property
  def supports_tracing(self):
    return True

  def StartTracing(self, trace_options, custom_categories=None,
                   timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    """
    Args:
        trace_options: An tracing_options.TracingOptions instance.
        custom_categories: An optional string containing a list of
                         comma separated categories that will be traced
                         instead of the default category set.  Example: use
                         "webkit,cc,disabled-by-default-cc.debug" to trace only
                         those three event categories.
    """
    assert trace_options and trace_options.enable_chrome_trace
    if self._tracing_backend is None:
      self._tracing_backend = tracing_backend.TracingBackend(self._port, self)
    return self._tracing_backend.StartTracing(
        trace_options, custom_categories, timeout)

  @property
  def is_tracing_running(self):
    if not self._tracing_backend:
      return None
    return self._tracing_backend.is_tracing_running

  def StopTracing(self):
    """ Stops tracing and returns the result as TimelineData object. """
    tab_ids_list = []
    for (i, _) in enumerate(self._browser.tabs):
      tab = self.tab_list_backend.Get(i, None)
      if tab:
        success = tab.EvaluateJavaScript(
            "console.time('" + tab.id + "');" +
            "console.timeEnd('" + tab.id + "');" +
            "console.time.toString().indexOf('[native code]') != -1;")
        if not success:
          raise Exception('Page stomped on console.time')
        tab_ids_list.append(tab.id)
    trace_events = self._tracing_backend.StopTracing()
    # Augment tab_ids data to trace events.
    event_data = {'traceEvents' : trace_events, 'tabIds': tab_ids_list}
    return tracing_timeline_data.TracingTimelineData(event_data)

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
