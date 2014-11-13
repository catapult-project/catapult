# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import user_agent
from telemetry.unittest_util import tab_test_case


class MobileUserAgentTest(tab_test_case.TabTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.browser_user_agent_type = 'mobile'

  def testUserAgent(self):
    ua = self._tab.EvaluateJavaScript('window.navigator.userAgent')
    self.assertEquals(ua, user_agent.UA_TYPE_MAPPING['mobile'])

class TabletUserAgentTest(tab_test_case.TabTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.browser_user_agent_type = 'tablet'

  def testUserAgent(self):
    ua = self._tab.EvaluateJavaScript('window.navigator.userAgent')
    self.assertEquals(ua, user_agent.UA_TYPE_MAPPING['tablet'])

class DesktopUserAgentTest(tab_test_case.TabTestCase):
  @classmethod
  def CustomizeBrowserOptions(cls, options):
    options.browser_user_agent_type = 'desktop'

  def testUserAgent(self):
    ua = self._tab.EvaluateJavaScript('window.navigator.userAgent')
    self.assertEquals(ua, user_agent.UA_TYPE_MAPPING['desktop'])
