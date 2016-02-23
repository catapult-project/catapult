# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import re
import unittest

import webapp2
import webtest

from dashboard import datastore_hooks
from dashboard import new_points
from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data


class NewPointsTest(testing_common.TestCase):

  def setUp(self):
    super(NewPointsTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/new_points', new_points.NewPointsHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@chromium.org', is_admin=True)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)

  def _AddSampleData(self):
    """Adds some normal test data from two different tests."""
    # Add Test entities.
    tests = {'foo': {'mytest': {}, 'other': {}}}
    testing_common.AddTests(['ChromiumPerf'], ['win7'], tests)
    mytest_key = utils.TestKey('ChromiumPerf/win7/foo/mytest')
    mytest_container = utils.GetTestContainerKey(mytest_key)
    other_key = utils.TestKey('ChromiumPerf/win7/foo/other')
    other_container = utils.GetTestContainerKey(other_key)

    # The times of the Row entities will have to be explicitly set, since being
    # ordered by time is part of what should be tested.
    start_date = datetime.datetime(2014, 1, 1, 0, 0)

    # Put some sample Rows in the datastore.
    for i in range(10):
      mytest_row = graph_data.Row(
          parent=mytest_container, id=(10000 + i), value=i)
      # Put it in twice so that the timestamp can be overwritten.
      mytest_row.put()
      mytest_row.timestamp = start_date + datetime.timedelta(hours=i)
      mytest_row.put()

      other_row = graph_data.Row(
          parent=other_container, id=(10000 + i), value=i)
      # Put it in twice so that the timestamp can be overwritten.
      other_row.put()
      other_row.timestamp = start_date + datetime.timedelta(hours=i, minutes=30)
      other_row.put()

  def _AddInternalSampleData(self):
    """Adds some internal-only test data."""
    master = graph_data.Master(id='XMaster').put()
    bot = graph_data.Bot(id='x-bot', parent=master, internal_only=True).put()
    test = graph_data.Test(id='xtest', parent=bot, internal_only=True).put()
    test_container_key = utils.GetTestContainerKey(test)
    for i in range(50):
      graph_data.Row(parent=test_container_key, id=i + 1000, value=i + 1000,
                     internal_only=True).put()

  def testGet_WithNoPattern_ListsPointsFromAllTests(self):
    """Tests a query for new points from all tests."""
    self._AddSampleData()
    response = self.testapp.get('/new_points')
    # 10 rows for mytest, 10 for other, 1 for the header.
    self.assertEqual(21, len(re.findall(r'<tr>', response.body)))

  def testGet_WithPattern_ListsPointsFromMatchingTests(self):
    """Tests a query for new points filtering by test pattern."""
    self._AddSampleData()
    response = self.testapp.get('/new_points',
                                {'pattern': 'ChromiumPerf/*/*/mytest'})
    # 10 rows for mytest, 1 for the header.
    self.assertEqual(11, len(re.findall(r'<tr>', response.body)))

  def testGet_QueryPatternWithNoMatches_ListsNoPoints(self):
    # When the users' query pattern has no matching test, the user should be
    # notified that this is the case.
    response = self.testapp.get('/new_points',
                                {'pattern': 'ImaginaryMaster/*/*/mytest'})
    self.assertTrue('No tests matching pattern' in response.body)
    self.assertEqual(1, len(re.findall(r'<tr>', response.body)))

  def testGet_InternalTestDataAuthorized_ShowsData(self):
    """Tests a query for internal data when the user should be authorized."""
    self._AddInternalSampleData()
    # The user doesn't need to be authorized as admin to view internal data,
    # they only need to have an internal email address.
    self.SetCurrentUser('internal@chromium.org')
    datastore_hooks.InstallHooks()
    response = self.testapp.get('/new_points')
    # 50 rows for xtest, 1 for the header.
    self.assertEqual(51, len(re.findall(r'<tr>', response.body)))

  def testGet_InternalTestDataUnauthorized_DoesntShowData(self):
    """Tests a query for internal data for an unauthorized user."""
    self._AddInternalSampleData()
    self.UnsetCurrentUser()
    datastore_hooks.InstallHooks()
    response = self.testapp.get('/new_points')
    # Only the header row is listed, not any others rows.
    self.assertEqual(1, len(re.findall(r'<tr>', response.body)))

  def testGet_WithMaxTestsParam(self):
    master = graph_data.Master(id='XMaster').put()
    bot = graph_data.Bot(id='x-bot', parent=master).put()
    for i in range(20):
      test = graph_data.Test(id='xtest-%d' % i, parent=bot).put()
      test_container_key = utils.GetTestContainerKey(test)
      graph_data.Row(parent=test_container_key, id=1, value=1).put()

    response = self.testapp.get(
        '/new_points', {'pattern': '*/*/*', 'max_tests': '12'})

    self.assertIn('matched 20 tests', response.body)
    self.assertIn('first 12 tests', response.body)
    # 12 points across 12 tests, plus one row for the header.
    self.assertEqual(13, len(re.findall(r'<tr>', response.body)))


if __name__ == '__main__':
  unittest.main()
