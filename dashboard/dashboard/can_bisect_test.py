# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import can_bisect
from dashboard import testing_common


class CanBisectTest(testing_common.TestCase):

  def setUp(self):
    super(CanBisectTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/can_bisect', can_bisect.CanBisectHandler)])
    self.testapp = webtest.TestApp(app)

  def testPost_BisectableTests_ReturnsTrue(self):
    response = self.testapp.post('/can_bisect', {
        'test_path': 'ChromiumPerf/mac/blink_perf.parser/simple-url',
        'start_revision': 123400,
        'end_revision': 123500,
    })
    self.assertEqual('true', response.body)

  def testPost_EmptyRequest_ReturnsFalse(self):
    response = self.testapp.post('/can_bisect', {})
    self.assertEqual('false', response.body)


if __name__ == '__main__':
  unittest.main()
