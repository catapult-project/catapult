# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.backends.chrome import chrome_browser_backend
from telemetry.core import wpr_modes


class FakePlatformBackend(object):
  def __init__(self, wpr_http_device_port, wpr_https_device_port,
               is_host_platform, does_forwarder_override_dns):
    self.wpr_http_device_port = wpr_http_device_port
    self.wpr_https_device_port = wpr_https_device_port
    self.does_forwarder_override_dns = does_forwarder_override_dns
    self.is_host_platform = is_host_platform

  @property
  def forwarder_factory(self):
    return FakeForwarderFactory(self.does_forwarder_override_dns)


class FakeBrowserOptions(object):
  def __init__(self, netsim=False, wpr_mode=wpr_modes.WPR_OFF):
    self.netsim = netsim
    self.wpr_mode = wpr_mode
    self.browser_type = 'chrome'
    self.dont_override_profile = False


class FakeForwarderFactory(object):
  host_ip = '127.0.0.1'

  def __init__(self, does_forwarder_override_dns):
    self.does_forwarder_override_dns = does_forwarder_override_dns


class TestChromeBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  # The test does not need to define the abstract methods. pylint: disable=W0223

  def __init__(self, browser_options, does_forwarder_override_dns=False,
               wpr_http_device_port=None, wpr_https_device_port=None,
               is_running_locally=False):
    super(TestChromeBrowserBackend, self).__init__(
        platform_backend=FakePlatformBackend(
            wpr_http_device_port, wpr_https_device_port, is_running_locally,
            does_forwarder_override_dns),
        supports_tab_control=False,
        supports_extensions=False,
        browser_options=browser_options,
        output_profile_path=None,
        extensions_to_load=None)


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

