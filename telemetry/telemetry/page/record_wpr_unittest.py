# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.page import page as page_module
from telemetry.page import record_wpr


class TestPage(page_module.Page):
  def __init__(self):
    super(TestPage, self).__init__(url='file://foo.html',
                                   page_set=None,
                                   base_dir=None)
    self.run_navigate = False
    self.run_foo = False
    self.run_bar = False

  def RunNavigateSteps(self, _):
    self.run_navigate = True

  def RunFoo(self, _):
    self.run_foo = True

  def RunBar(self, _):
    self.run_bar = True


class FakeFooMeasurement(object):
  def __init__(self):
    self.action_name_to_run = "RunFoo"


class FakeBarMeasurement(object):
  def __init__(self):
    self.action_name_to_run = "RunBar"


class FakeTab(object):
  def WaitForDocumentReadyStateToBeComplete(self):
    pass


class RecordWprUnitTest(unittest.TestCase):
  def setUp(self):
    super(RecordWprUnitTest, self).setUp()

  def testRunActions(self):
    page = TestPage()
    record_runner = record_wpr.RecordPage({1 : FakeFooMeasurement,
                                           2 : FakeBarMeasurement})
    record_runner.RunPage(page, tab=FakeTab(), results=None)
    self.assertTrue(page.run_navigate)
    self.assertTrue(page.run_foo)
    self.assertTrue(page.run_bar)

