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

from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import extension_backend
from telemetry.core.backends.chrome import system_info_backend
from telemetry.core.backends.chrome import tab_list_backend
from telemetry.core.backends.chrome_inspector import devtools_client_backend
from telemetry.core.backends.chrome_inspector import devtools_http
from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import user_agent
from telemetry.core import util
from telemetry.core import web_contents
from telemetry.core import wpr_modes
from telemetry import decorators
from telemetry.unittest_util import options_for_unittests


class ChromeBrowserBackend(browser_backend.BrowserBackend):
  """An abstract class for chrome browser backends. Provides basic functionality
  once a remote-debugger port has been established."""
  # It is OK to have abstract methods. pylint: disable=W0223

  def __init__(self, platform_backend, supports_tab_control,
               supports_extensions, browser_options, output_profile_path,
               extensions_to_load):
    super(ChromeBrowserBackend, self).__init__(
        platform_backend=platform_backend,
        supports_extensions=supports_extensions,
        browser_options=browser_options,
        tab_list_backend=tab_list_backend.TabListBackend)
    self._port = None

    self._supports_tab_control = supports_tab_control
    self._devtools_client = None
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

  @property
  def devtools_client(self):
    return self._devtools_client

  @property
  @decorators.Cache
  def extension_backend(self):
    if not self.supports_extensions:
      return None
    return extension_backend.ExtensionBackendDict(self)

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.browser_options.extra_browser_args)
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

    if self.browser_options.disable_background_networking:
      args.append('--disable-background-networking')
    args.extend(self.GetReplayBrowserStartupArgs())
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

    # Disables the start page, as well as other external apps that can
    # steal focus or make measurements inconsistent.
    if self.browser_options.disable_default_apps:
      args.append('--disable-default-apps')

    return args

  def _UseHostResolverRules(self):
    """Returns True to add --host-resolver-rules to send requests to replay."""
    if self._platform_backend.forwarder_factory.does_forwarder_override_dns:
      # Avoid --host-resolver-rules when the forwarder will map DNS requests
      # from the target platform to replay (on the host platform).
      # This allows the browser to exercise DNS requests.
      return False
    if self.browser_options.netsim and self.platform_backend.is_host_platform:
      # Avoid --host-resolver-rules when replay will configure the platform to
      # resolve hosts to replay.
      # This allows the browser to exercise DNS requests.
      return False
    return True

  def GetReplayBrowserStartupArgs(self):
    if self.browser_options.wpr_mode == wpr_modes.WPR_OFF:
      return []
    replay_args = []
    if self.should_ignore_certificate_errors:
      # Ignore certificate errors if the platform backend has not created
      # and installed a root certificate.
      replay_args.append('--ignore-certificate-errors')
    if self._UseHostResolverRules():
      # Force hostnames to resolve to the replay's host_ip.
      replay_args.append('--host-resolver-rules=MAP * %s,EXCLUDE localhost' %
                         self._platform_backend.forwarder_factory.host_ip)
    # Force the browser to send HTTP/HTTPS requests to fixed ports if they
    # are not the standard HTTP/HTTPS ports.
    http_port = self.platform_backend.wpr_http_device_port
    https_port = self.platform_backend.wpr_https_device_port
    if http_port != 80:
      replay_args.append('--testing-fixed-http-port=%s' % http_port)
    if https_port != 443:
      replay_args.append('--testing-fixed-https-port=%s' % https_port)
    return replay_args

  def HasBrowserFinishedLaunching(self):
    assert self._port, 'No DevTools port info available.'
    return devtools_client_backend.IsDevToolsAgentAvailable(self._port)

  def _InitDevtoolsClientBackend(self, remote_devtools_port=None):
    """ Initiate the devtool client backend which allow browser connection
    through browser' devtool.

    Args:
      remote_devtools_port: The remote devtools port, if
          any. Otherwise assumed to be the same as self._port.
    """
    assert not self._devtools_client, (
        'Devtool client backend cannot be init twice')
    self._devtools_client = devtools_client_backend.DevToolsClientBackend(
        self._port, remote_devtools_port or self._port, self)

  def _WaitForBrowserToComeUp(self):
    """ Wait for browser to come up. """
    try:
      util.WaitFor(self.HasBrowserFinishedLaunching, timeout=30)
    except (exceptions.TimeoutException, exceptions.ProcessGoneException) as e:
      if not self.IsBrowserRunning():
        raise exceptions.BrowserGoneException(self.browser, e)
      raise exceptions.BrowserConnectionGoneException(self.browser, e)

  def _WaitForExtensionsToLoad(self):
    """ Wait for all extensions to load.
    Be sure to check whether the browser_backend supports_extensions before
    calling this method.
    """
    assert self._supports_extensions
    assert self._devtools_client, (
        'Waiting for extensions required devtool client to be initiated first')
    try:
      util.WaitFor(self._AllExtensionsLoaded, timeout=60)
    except exceptions.TimeoutException:
      logging.error('ExtensionsToLoad: ' +
          repr([e.extension_id for e in self._extensions_to_load]))
      logging.error('Extension list: ' +
          pprint.pformat(self.extension_backend, indent=4))
      raise

  def _AllExtensionsLoaded(self):
    # Extension pages are loaded from an about:blank page,
    # so we need to check that the document URL is the extension
    # page in addition to the ready state.
    extension_ready_js = """
        document.URL.lastIndexOf('chrome-extension://%s/', 0) == 0 &&
        (document.readyState == 'complete' ||
         document.readyState == 'interactive')
    """
    for e in self._extensions_to_load:
      try:
        extension_objects = self.extension_backend[e.extension_id]
      except KeyError:
        return False
      for extension_object in extension_objects:
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

  @property
  def browser_directory(self):
    raise NotImplementedError()

  @property
  def profile_directory(self):
    raise NotImplementedError()

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
    return self.devtools_client.StartChromeTracing(
        trace_options, custom_categories, timeout)

  def StopTracing(self, trace_data_builder):
    self.devtools_client.StopChromeTracing(trace_data_builder)

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
    if self._devtools_client:
      self._devtools_client.Close()
      self._devtools_client = None

  @property
  def supports_system_info(self):
    return self.GetSystemInfo() != None

  def GetSystemInfo(self):
    if self._system_info_backend is None:
      self._system_info_backend = system_info_backend.SystemInfoBackend(
          self._port)
    return self._system_info_backend.GetSystemInfo()
