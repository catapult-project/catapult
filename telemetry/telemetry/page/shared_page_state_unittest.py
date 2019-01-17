# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import platform as platform_module
from telemetry.page import page
from telemetry.page import legacy_page_test
from telemetry.page import shared_page_state
from telemetry import story as story_module
from telemetry.testing import fakes
from telemetry.util import wpr_modes


class DummyTest(legacy_page_test.LegacyPageTest):

  def ValidateAndMeasurePage(self, *_):
    pass


class SharedPageStateTests(unittest.TestCase):

  def setUp(self):
    self.options = fakes.CreateBrowserFinderOptions()
    self.options.pause = None
    self.options.use_live_sites = False
    self.options.output_formats = ['none']
    self.options.suppress_gtest_report = True

  def testUseLiveSitesFlagSet(self):
    self.options.use_live_sites = True
    run_state = shared_page_state.SharedPageState(
        DummyTest(), self.options, story_module.StorySet())
    try:
      self.assertTrue(run_state.platform.network_controller.is_open)
      self.assertEquals(run_state.platform.network_controller.wpr_mode,
                        wpr_modes.WPR_OFF)
      self.assertTrue(run_state.platform.network_controller.use_live_traffic)
    finally:
      run_state.TearDownState()

  def testUseLiveSitesFlagUnset(self):
    run_state = shared_page_state.SharedPageState(
        DummyTest(), self.options, story_module.StorySet())
    try:
      self.assertTrue(run_state.platform.network_controller.is_open)
      self.assertEquals(run_state.platform.network_controller.wpr_mode,
                        wpr_modes.WPR_REPLAY)
      self.assertFalse(run_state.platform.network_controller.use_live_traffic)
    finally:
      run_state.TearDownState()

  def testWPRRecordEnable(self):
    self.options.browser_options.wpr_mode = wpr_modes.WPR_RECORD
    run_state = shared_page_state.SharedPageState(
        DummyTest(), self.options, story_module.StorySet())
    try:
      self.assertTrue(run_state.platform.network_controller.is_open)
      self.assertEquals(run_state.platform.network_controller.wpr_mode,
                        wpr_modes.WPR_RECORD)
      self.assertFalse(run_state.platform.network_controller.use_live_traffic)
    finally:
      run_state.TearDownState()

  def testConstructorCallsSetOptions(self):
    test = DummyTest()
    run_state = shared_page_state.SharedPageState(
        test, self.options, story_module.StorySet())
    try:
      self.assertEqual(test.options, self.options)
    finally:
      run_state.TearDownState()

  def assertUserAgentSetCorrectly(
      self, shared_page_state_class, expected_user_agent):
    story = page.Page(
        'http://www.google.com',
        shared_page_state_class=shared_page_state_class,
        name='Google')
    test = DummyTest()
    story_set = story_module.StorySet()
    story_set.AddStory(story)
    run_state = story.shared_state_class(test, self.options, story_set)
    try:
      browser_options = self.options.browser_options
      actual_user_agent = browser_options.browser_user_agent_type
      self.assertEqual(expected_user_agent, actual_user_agent)
    finally:
      run_state.TearDownState()

  def testPageStatesUserAgentType(self):
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedMobilePageState, 'mobile')
    if platform_module.GetHostPlatform().GetOSName() == 'chromeos':
      self.assertUserAgentSetCorrectly(
          shared_page_state.SharedDesktopPageState, 'chromeos')
    else:
      self.assertUserAgentSetCorrectly(
          shared_page_state.SharedDesktopPageState, 'desktop')
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedTabletPageState, 'tablet')
    self.assertUserAgentSetCorrectly(
        shared_page_state.Shared10InchTabletPageState, 'tablet_10_inch')
    self.assertUserAgentSetCorrectly(
        shared_page_state.SharedPageState, None)
