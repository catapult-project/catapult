# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for report module."""

__author__ = 'sullivan@google.com (Annie Sullivan)'

import unittest

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import report
from dashboard import testing_common
from dashboard import update_test_suites


class ReportTest(testing_common.TestCase):

  def setUp(self):
    super(ReportTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/report', report.ReportHandler),
         ('/update_test_suites', update_test_suites.UpdateTestSuitesHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddTestSuites(self):
    """Adds sample data and sets the list of test suites."""
    # Mock out some data for a test.
    masters = [
        'ChromiumPerf',
        'ChromiumGPU',
    ]
    bots = [
        'chromium-rel-win7-gpu-ati',
        'linux-release',
    ]
    tests = {
        'scrolling_benchmark': {
            'average_commit_time': {
                'answers.yahoo.com': {},
                'www.cnn.com': {},
            },
            'average_commit_time_ref': {},
        },
        'dromaeo': {},
    }
    testing_common.AddDataToMockDataStore(masters, bots, tests)
    for m in masters:
      for b in bots:
        for t in tests:
          t = ndb.Key('Master', m, 'Bot', b, 'Test', t).get()
          t.description = 'This should show up'
          t.put()

    # Before the test suites data gets generated, the cached test suites
    # data must be updated.
    self.testapp.post('/update_test_suites')

  def testGet_EmbedsTestSuites(self):
    self._AddTestSuites()

    # We expect to have this JavaScript in the rendered HTML.
    expected_suites = {
        'scrolling_benchmark': {
            'masters': {
                'ChromiumPerf': ['chromium-rel-win7-gpu-ati', 'linux-release'],
                'ChromiumGPU': ['chromium-rel-win7-gpu-ati', 'linux-release'],
            },
            'monitored': [],
            'description': 'This should show up',
            'deprecated': False,
        },
        'dromaeo': {
            'masters': {
                'ChromiumPerf': ['chromium-rel-win7-gpu-ati', 'linux-release'],
                'ChromiumGPU': ['chromium-rel-win7-gpu-ati', 'linux-release'],
            },
            'monitored': [],
            'description': 'This should show up',
            'deprecated': False,
        },
    }
    response = self.testapp.get('/report')
    actual_suites = testing_common.GetEmbeddedVariable(response, 'TEST_SUITES')
    self.assertEqual(expected_suites, actual_suites)


if __name__ == '__main__':
  unittest.main()
