# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import tempfile
import unittest

from telemetry.internal import story_runner
from telemetry.page import page
from telemetry.page import page_test
from telemetry.page import shared_page_state
from telemetry import story as story_module
from telemetry.testing import fakes
from telemetry.testing import options_for_unittests
from telemetry.util import wpr_modes

import mock


def SetUpPageRunnerArguments(options):
  parser = options.CreateParser()
  story_runner.AddCommandLineArgs(parser)
  options.MergeDefaultValues(parser.get_default_values())
  story_runner.ProcessCommandLineArgs(parser, options)


class DummyTest(page_test.PageTest):
  def ValidateAndMeasurePage(self, *_):
    pass


class FakeNetworkController(object):
  def __init__(self):
    self.archive_path = None
    self.wpr_mode = None

  def SetReplayArgs(self, archive_path, wpr_mode, _netsim, _extra_wpr_args,
                    _make_javascript_deterministic=False):
    self.archive_path = archive_path
    self.wpr_mode = wpr_mode


class SharedPageStateTests(unittest.TestCase):

  def setUp(self):
    self.options = options_for_unittests.GetCopy()
    SetUpPageRunnerArguments(self.options)
    self.options.output_formats = ['none']
    self.options.suppress_gtest_report = True
    self.patcher = mock.patch(
        'telemetry.page.shared_page_state.browser_finder.FindBrowser')
    find_browser_mock = self.patcher.start()
    find_browser_mock.return_value = fakes.FakePossibleBrowser()

  def tearDown(self):
    mock.patch.stopall()

  # pylint: disable=W0212
  def TestUseLiveSitesFlag(self, expected_wpr_mode):
    with tempfile.NamedTemporaryFile() as f:
      run_state = shared_page_state.SharedPageState(
          DummyTest(), self.options, story_module.StorySet())
      fake_network_controller = FakeNetworkController()
      run_state._PrepareWpr(fake_network_controller, f.name, None)
      self.assertEquals(fake_network_controller.wpr_mode, expected_wpr_mode)
      self.assertEquals(fake_network_controller.archive_path, f.name)

  def testUseLiveSitesFlagSet(self):
    self.options.use_live_sites = True
    self.TestUseLiveSitesFlag(expected_wpr_mode=wpr_modes.WPR_OFF)

  def testUseLiveSitesFlagUnset(self):
    self.TestUseLiveSitesFlag(expected_wpr_mode=wpr_modes.WPR_REPLAY)

  def testConstructorCallsSetOptions(self):
    test = DummyTest()
    shared_page_state.SharedPageState(
        test, self.options, story_module.StorySet())
    self.assertEqual(test.options, self.options)

  def assertUserAgentSetCorrectly(
      self, shared_page_state_class, expected_user_agent):
    story = page.Page(
        'http://www.google.com',
        shared_page_state_class=shared_page_state_class)
    test = DummyTest()
    story_set = story_module.StorySet()
    story_set.AddStory(story)
    story.shared_state_class(test, self.options, story_set)
    browser_options = self.options.browser_options
    actual_user_agent = browser_options.browser_user_agent_type
    self.assertEqual(expected_user_agent, actual_user_agent)

  def testPageStatesUserAgentType(self):
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedMobilePageState, 'mobile')
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedDesktopPageState, 'desktop')
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedTabletPageState, 'tablet')
    self.assertUserAgentSetCorrectly(
        shared_page_state.Shared10InchTabletPageState, 'tablet_10_inch')
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedPageState, None)

  def testBrowserStartupURLSetCorrectly(self):
    story_set = story_module.StorySet()
    google_page = page.Page(
        'http://www.google.com',
        startup_url='http://www.google.com', page_set=story_set)
    example_page = page.Page(
        'https://www.example.com',
        startup_url='https://www.example.com', page_set=story_set)
    gmail_page = page.Page(
        'https://www.gmail.com',
        startup_url='https://www.gmail.com', page_set=story_set)

    for p in (google_page, example_page, gmail_page):
      story_set.AddStory(p)

    mock_finder_options = mock.Mock()
    mock_finder_options.profiler = None

    shared_state = shared_page_state.SharedPageState(
        DummyTest(), mock_finder_options, story_set)

    for p in (google_page, example_page, gmail_page):
      shared_state.WillRunStory(p)
      self.assertEquals(
        p.startup_url, mock_finder_options.browser_options.startup_url)
      shared_state.TearDownState()
