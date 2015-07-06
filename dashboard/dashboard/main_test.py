# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for 'main' module (the request handler for the front page)."""

import unittest

import mock
import webapp2
import webtest

from dashboard import main
from dashboard import testing_common


class MainTest(testing_common.TestCase):

  def setUp(self):
    super(MainTest, self).setUp()
    app = webapp2.WSGIApplication([('/', main.MainHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(
          return_value=testing_common.FakeResponseObject(500, '(fail)')))
  def testGet_BugRequestFails_PageIsShown(self):
    """Even if the recent bugs list can't be fetched, the page should load."""
    response = self.testapp.get('/')
    self.assertIn('<html>', response.body)


if __name__ == '__main__':
  unittest.main()
