# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import forwarders
from telemetry.core import wpr_modes
from telemetry.core.backends.chrome import chrome_browser_backend


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

  def __init__(self, browser_options, does_forwarder_override_dns=False):
    super(TestChromeBrowserBackend, self).__init__(
        platform_backend=None,
        supports_tab_control=False,
        supports_extensions=False,
        browser_options=browser_options,
        output_profile_path=None,
        extensions_to_load=None)
    self._forwarder_factory = FakeForwarderFactory(does_forwarder_override_dns)


class ReplayStartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetReplayBrowserStartupArgs."""

  def testReplayOffGivesEmptyArgs(self):
    browser_options = FakeBrowserOptions()
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertEqual([], browser_backend.GetReplayBrowserStartupArgs())

  def testReplayOnGivesBasicArgs(self):
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=False)
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertEqual((0, 0), tuple(browser_backend.wpr_port_pairs.http))
    self.assertEqual((0, 0), tuple(browser_backend.wpr_port_pairs.https))
    self.assertEqual(None, browser_backend.wpr_port_pairs.dns)

    # When Replay is started, it fills in the actual port values.
    # Use different values here to show that the args get the
    # remote port values.
    browser_backend.wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(123, 456),
        https=forwarders.PortPair(234, 567),
        dns=None)
    expected_args = [
        '--host-resolver-rules=MAP * 127.0.0.1,EXCLUDE localhost',
        '--ignore-certificate-errors',
        '--testing-fixed-http-port=456',
        '--testing-fixed-https-port=567'
        ]
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def testNetsimGivesNoHostResolver(self):
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=True)
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertEqual((80, 80), tuple(browser_backend.wpr_port_pairs.http))
    self.assertEqual((443, 443), tuple(browser_backend.wpr_port_pairs.https))
    self.assertEqual((53, 53), tuple(browser_backend.wpr_port_pairs.dns))
    expected_args = ['--ignore-certificate-errors']
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def testForwaderOverridesDnsGivesNoHostResolver(self):
    # Android with --use-rndis uses standard remote ports and
    # relies on the forwarder to override DNS resolution.
    browser_options = FakeBrowserOptions(
        wpr_mode=wpr_modes.WPR_REPLAY,
        netsim=False)
    browser_backend = TestChromeBrowserBackend(
        browser_options, does_forwarder_override_dns=True)
    browser_backend.wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(123, 80),
        https=forwarders.PortPair(234, 443),
        dns=forwarders.PortPair(345, 53))
    expected_args = ['--ignore-certificate-errors']
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))
