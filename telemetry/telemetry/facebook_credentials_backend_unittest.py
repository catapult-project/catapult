# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import browser_finder
from telemetry import facebook_credentials_backend
from telemetry import simple_mock
from telemetry import options_for_unittests

_ = simple_mock.DONT_CARE

class MockTab(simple_mock.MockObject):
  def __init__(self):
    super(MockTab, self).__init__()
    self.runtime = simple_mock.MockObject(self)
    self.page = simple_mock.MockObject(self)

class TestFacebookCredentialsBackend(unittest.TestCase):
  def testRealLoginIfPossible(self):
    credentials_path = os.path.join(
      os.path.dirname(__file__),
      '..', '..', 'perf', 'data', 'credentials.json')
    if not os.path.exists(credentials_path):
      return

    options = options_for_unittests.GetCopy()
    with browser_finder.FindBrowser(options).Create() as b:
      b.credentials.credentials_path = credentials_path
      if not b.credentials.CanLogin('facebook'):
        return
      ret = b.credentials.LoginNeeded(b.tabs[0], 'facebook')
      self.assertTrue(ret)

  def testRealLoginWithDontOverrideProfileIfPossible(self):
    credentials_path = os.path.join(
      os.path.dirname(__file__),
      '..', '..', 'perf', 'data', 'credentials.json')
    if not os.path.exists(credentials_path):
      return

    options = options_for_unittests.GetCopy()
    options.dont_override_profile = True

    # Login once to make sure our default profile is logged in.
    with browser_finder.FindBrowser(options).Create() as b:
      b.credentials.credentials_path = credentials_path
      if not b.credentials.CanLogin('facebook'):
        return
      ret = b.credentials.LoginNeeded(b.tabs[0], 'facebook')
      self.assertTrue(ret)

    # Second time will test that we behave correctly if we're logged in,
    # but our b.credentials doesn't know yet.
    with browser_finder.FindBrowser(options).Create() as b:
      b.credentials.credentials_path = credentials_path
      if not b.credentials.CanLogin('facebook'):
        return
      ret = b.credentials.LoginNeeded(b.tabs[0], 'facebook')
      self.assertTrue(ret)

  def testLoginUsingMock(self): # pylint: disable=R0201
    tab = MockTab()

    backend = facebook_credentials_backend.FacebookCredentialsBackend()
    config = {'username': 'blah',
              'password': 'blargh'}

    tab.page.ExpectCall('Navigate', 'http://www.facebook.com/')
    tab.runtime.ExpectCall('Evaluate', _).WillReturn(False)
    tab.runtime.ExpectCall('Evaluate', _).WillReturn(True)
    tab.runtime.ExpectCall('Evaluate', _).WillReturn(False)
    tab.ExpectCall('WaitForDocumentReadyStateToBeInteractiveOrBetter')

    def VerifyEmail(js):
      assert 'email' in js
      assert 'blah' in js
    tab.runtime.ExpectCall('Execute', _).WhenCalled(VerifyEmail)

    def VerifyPw(js):
      assert 'pass' in js
      assert 'largh' in js
    tab.runtime.ExpectCall('Execute', _).WhenCalled(VerifyPw)

    def VerifySubmit(js):
      assert '.submit' in js
    tab.runtime.ExpectCall('Execute', _).WhenCalled(VerifySubmit)

    # Checking for form still up.
    tab.runtime.ExpectCall('Evaluate', _).WillReturn(False)

    backend.LoginNeeded(tab, config)

