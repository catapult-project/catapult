# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import mock

from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.browser import browser_options as browser_options_module
from telemetry.util import wpr_modes


class FakePlatformBackend(object):
  def __init__(self, is_network_controller_open, local_ts_proxy_port,
               remote_port, is_host_platform):
    self.is_host_platform = is_host_platform

    self.forwarder_factory = mock.Mock()

    self.network_controller_backend = mock.Mock()
    self.network_controller_backend.is_open = is_network_controller_open
    if is_network_controller_open:
      self.network_controller_backend.forwarder.local_port = local_ts_proxy_port
      self.network_controller_backend.forwarder.remote_port = remote_port
    else:
      self.network_controller_backend.forwarder = None
    self.network_controller_backend.host_ip = '127.0.0.1'
    self.network_controller_backend.is_test_ca_installed = False


class FakeBrowserOptions(browser_options_module.BrowserOptions):
  def __init__(self, wpr_mode=wpr_modes.WPR_OFF):
    super(FakeBrowserOptions, self).__init__()
    self.wpr_mode = wpr_mode
    self.browser_type = 'chrome'
    self.browser_user_agent_type = 'desktop'
    self.disable_background_networking = False
    self.disable_component_extensions_with_background_pages = False
    self.disable_default_apps = False


class TestChromeBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  # The test does not need to define the abstract methods.
  # pylint: disable=abstract-method

  def __init__(self, browser_options,
               local_ts_proxy_port=None,
               remote_port=None,
               is_running_locally=False):
    browser_options.extensions_to_load = []
    browser_options.output_profile_path = None
    super(TestChromeBrowserBackend, self).__init__(
        platform_backend=FakePlatformBackend(
            browser_options.wpr_mode != wpr_modes.WPR_OFF,
            local_ts_proxy_port, remote_port, is_running_locally),
        supports_tab_control=False,
        supports_extensions=False,
        browser_options=browser_options)


class ReplayStartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetReplayBrowserStartupArgs."""

  def testReplayOffGivesEmptyArgs(self):
    browser_options = FakeBrowserOptions()
    browser_backend = TestChromeBrowserBackend(browser_options)
    self.assertEqual([], browser_backend.GetReplayBrowserStartupArgs())

  def BasicArgsHelper(self, is_running_locally):
    browser_options = FakeBrowserOptions(wpr_mode=wpr_modes.WPR_REPLAY)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        local_ts_proxy_port=567,
        remote_port=789,
        is_running_locally=is_running_locally)
    expected_args = [
        '--ignore-certificate-errors-spki-list='
        'PhrPvGIaAMmd29hj8BCZOq096yj7uMpRNHpn5PDxI6I=',
        '--proxy-server=socks://localhost:789',
        ]
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

  def testBasicArgs(self):
    # The result is the same regardless of whether running locally.
    self.BasicArgsHelper(is_running_locally=True)
    self.BasicArgsHelper(is_running_locally=False)

  def testReplayNotActive(self):
    browser_options = FakeBrowserOptions(wpr_mode=wpr_modes.WPR_OFF)
    browser_backend = TestChromeBrowserBackend(
        browser_options,
        local_ts_proxy_port=567,
        remote_port=789,
        is_running_locally=True)
    expected_args = []
    self.assertEqual(
        expected_args,
        sorted(browser_backend.GetReplayBrowserStartupArgs()))

class StartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetBrowserStartupArgs."""

  def testFeaturesMerged(self):
    browser_options = FakeBrowserOptions()
    browser_options.AppendExtraBrowserArgs([
        '--disable-features=Feature1,Feature2',
        '--disable-features=Feature2,Feature3',
        '--enable-features=Feature4,Feature5',
        '--enable-features=Feature5,Feature6',
        '--foo'])
    browser_backend = TestChromeBrowserBackend(browser_options)

    startup_args = browser_backend.GetBrowserStartupArgs()
    self.assertTrue('--foo' in startup_args)
    # Make sure there's only once instance of --enable/disable-features and it
    # contains all values
    disable_count = 0
    enable_count = 0
    # Merging is done using using sets, so any order is correct
    for arg in startup_args:
      if arg.startswith('--disable-features='):
        split_arg = arg.split('=', 1)[1].split(',')
        self.assertEquals({'Feature1', 'Feature2', 'Feature3'}, set(split_arg))
        disable_count += 1
      elif arg.startswith('--enable-features='):
        split_arg = arg.split('=', 1)[1].split(',')
        self.assertEquals({'Feature4', 'Feature5', 'Feature6'}, set(split_arg))
        enable_count += 1
    self.assertEqual(1, disable_count)
    self.assertEqual(1, enable_count)
