# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import can_bisect
from dashboard import testing_common
from dashboard import namespaced_stored_object


class CanBisectTest(testing_common.TestCase):

  def setUp(self):
    super(CanBisectTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/can_bisect', can_bisect.CanBisectHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.SetCurrentUser('internal@chromium.org')
    namespaced_stored_object.Set(
        can_bisect.BISECT_BOT_MAP_KEY,
        {'SupportedMaster': ['perf_bot', 'bisect_bot']})

  def testPost_BisectableTests_ReturnsTrue(self):
    response = self.testapp.post('/can_bisect', {
        'test_path': 'SupportedMaster/mac/blink_perf.parser/simple-url',
        'start_revision': 123400,
        'end_revision': 123500,
    })
    self.assertEqual('true', response.body)

  def testPost_UnsupportedMaster_ReturnsFalse(self):
    response = self.testapp.post('/can_bisect', {
        'test_path': 'UnsupportedMaster/mac/blink_perf.parser/simple-url',
        'start_revision': 123400,
        'end_revision': 123500,
    })
    self.assertEqual('false', response.body)

  def testPost_EmptyRequest_ReturnsFalse(self):
    response = self.testapp.post('/can_bisect', {})
    self.assertEqual('false', response.body)

  def testIsValidTestForBisect_Supported_ReturnsTrue(self):
    self.assertTrue(
        can_bisect.IsValidTestForBisect('SupportedMaster/b/t/foo'))

  def testIsValidTestForBisect_RefTest_ReturnsFalse(self):
    self.assertFalse(
        can_bisect.IsValidTestForBisect('SupportedMaster/b/t/ref'))

  def testIsValidTestForBisect_UnsupportedMaster_ReturnsFalse(self):
    self.assertFalse(
        can_bisect.IsValidTestForBisect('X/b/t/foo'))


if __name__ == '__main__':
  unittest.main()
