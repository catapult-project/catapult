# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import mock

from telemetry.internal import forwarders
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.util import wpr_modes


class FakePlatformBackend(object):
  def __init__(self, is_replay_active, wpr_http_device_port,
               wpr_https_device_port, is_host_platform,
               does_forwarder_override_dns):
    self.is_host_platform = is_host_platform

    self.forwarder_factory = mock.Mock()
    self.forwarder_factory.does_forwarder_override_dns = (
        does_forwarder_override_dns)

    self.network_controller_backend = mock.Mock()
    self.network_controller_backend.is_replay_active = is_replay_active
    self.network_controller_backend.wpr_device_ports = forwarders.PortSet(
        http=wpr_http_device_port, https=wpr_https_device_port, dns=None)
    self.network_controller_backend.host_ip = '127.0.0.1'
    self.network_controller_backend.is_test_ca_installed = False


class FakeBrowserOptions(object):
  def __init__(self, netsim=False, wpr_mode=wpr_modes.WPR_OFF):
    self.netsim = netsim
    self.wpr_mode = wpr_mode
    self.browser_type = 'chrome'
    self.dont_override_profile = False
    self.browser_user_agent_type = 'desktop'
    self.disable_background_networking = False
    self.disable_component_extensions_with_background_pages = False
    self.disable_default_apps = False
    self.extra_browser_args = []
    self.no_proxy_server = False
    self.enable_logging = False


class TestChromeBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  # The test does not need to define the abstract methods.
  # pylint: disable=abstract-method

  def __init__(self, browser_options, does_forwarder_override_dns=False,
               wpr_http_device_port=None, wpr_https_device_port=None,
               is_running_locally=False):
    super(TestChromeBrowserBackend, self).__init__(
        platform_backend=FakePlatformBackend(
            browser_options.wpr_mode != wpr_modes.WPR_OFF,
            wpr_http_device_port, wpr_https_device_port, is_running_locally,
            does_forwarder_override_dns),
        supports_tab_control=False,
        supports_extensions=False,
        browser_options=browser_options,
        output_profile_path=None,
        extensions_to_load=[])


class StartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetBrowserStartupArgs."""

  def testNoProxyServer(self):
    browser_options = FakeBrowserOptions()
    browser_options.no_proxy_server = False
    browser_options.extra_browser_args = ['--proxy-server=http=inter.net']
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertNotIn('--no-proxy-server',
                     browser_backend.GetBrowserStartupArgs())

    browser_options.no_proxy_server = True
    self.assertIn('--no-proxy-server', browser_backend.GetBrowserStartupArgs())

class ReplayStartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetReplayBrowserStartupArgs."""

  def testReplayOffGivesEmptyArgs(self):
    browser_options = FakeBrowserOptions()
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertEqual([], browser_backend.GetReplayBrowserStartupArgs())

  def BasicArgsHelper(self, is_running_locally):
    # Covers Android without RNDIS and CrOS.
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=False)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        does_forwarder_override_dns=False,
        wpr_http_device_port=456,
        wpr_https_device_port=567,
        is_running_locally=is_running_locally)
    expected_args = [
        '--host-resolver-rules=MAP * 127.0.0.1,EXCLUDE localhost',
        '--ignore-certificate-errors',
        '--testing-fixed-http-port=456',
        '--testing-fixed-https-port=567'
        ]
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def testBasicArgs(self):
    # The result is the same regardless of whether running locally.
    self.BasicArgsHelper(is_running_locally=True)
    self.BasicArgsHelper(is_running_locally=False)

  def testDesktopNetsimGivesNoFixedPortsNorHostResolverRules(self):
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=True)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        does_forwarder_override_dns=False,
        wpr_http_device_port=80,
        wpr_https_device_port=443,
        is_running_locally=True)
    expected_args = ['--ignore-certificate-errors']
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def ForwarderOverridesDnsHelper(self, is_netsim):
    # Android with --use-rndis uses standard remote ports and
    # relies on the forwarder to override DNS resolution.
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=is_netsim)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        does_forwarder_override_dns=True,
        wpr_http_device_port=80,
        wpr_https_device_port=443,
        is_running_locally=False)
    expected_args = ['--ignore-certificate-errors']
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def testAndroidRndisGivesNoFixedPortsNorHostResolverRules(self):
    # The result is the same regardless of netsim setting.
    self.ForwarderOverridesDnsHelper(is_netsim=True)
    self.ForwarderOverridesDnsHelper(is_netsim=False)

  def testRemoteCrOsNetsimStillUsesHostResolver(self):
    # CrOS has not implemented the forwarder override for DNS.
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=True)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        does_forwarder_override_dns=False,
        wpr_http_device_port=80,
        wpr_https_device_port=443,
        is_running_locally=False)
    expected_args = [
        '--host-resolver-rules=MAP * 127.0.0.1,EXCLUDE localhost',
        '--ignore-certificate-errors',
        ]
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))
