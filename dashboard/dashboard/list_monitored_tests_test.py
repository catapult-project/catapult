# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import webapp2
import webtest

from dashboard import list_monitored_tests
from dashboard import testing_common
from dashboard.models import graph_data
from dashboard.models import sheriff


class ListMonitoredTestsTest(testing_common.TestCase):

  def setUp(self):
    super(ListMonitoredTestsTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/list_monitored_tests',
          list_monitored_tests.ListMonitoredTestsHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddSampleTestData(self):
    """Adds some sample data used in the tests below."""
    master = graph_data.Master(id='TheMaster').put()
    bot = graph_data.Bot(id='TheBot', parent=master).put()
    suite1 = graph_data.Test(id='Suite1', parent=bot).put()
    suite2 = graph_data.Test(id='Suite2', parent=bot).put()
    graph_data.Test(id='aaa', parent=suite1, has_rows=True).put()
    graph_data.Test(id='bbb', parent=suite1, has_rows=True).put()
    graph_data.Test(id='ccc', parent=suite2, has_rows=True).put()
    graph_data.Test(id='ddd', parent=suite2, has_rows=True).put()

  def _AddSheriff(self, name, email=None, url=None,
                  internal_only=False, summarize=False, patterns=None):
    """Adds a Sheriff entity to the datastore."""
    sheriff.Sheriff(
        id=name, email=email, url=url, internal_only=internal_only,
        summarize=summarize, patterns=patterns or []).put()

  def testGet_ValidSheriff_ReturnsJSONListOfTests(self):
    self._AddSheriff('X', patterns=['*/*/Suite1/*'])
    self._AddSampleTestData()
    response = self.testapp.get(
        '/list_monitored_tests', {'get-sheriffed-by': 'X'})
    self.assertEqual(
        ['TheMaster/TheBot/Suite1/aaa', 'TheMaster/TheBot/Suite1/bbb'],
        json.loads(response.body))

  def testGet_NoParameterGiven_ReturnsError(self):
    # This would raise an exception (and fail the test) if the status
    # doesn't match the given status.
    self.testapp.get('/list_monitored_tests', status=400)

  def testGet_NonExistentSheriff_ReturnsJSONEmptyList(self):
    response = self.testapp.get(
        '/list_monitored_tests', {'get-sheriffed-by': 'Bogus Sheriff'})
    self.assertEqual([], json.loads(response.body))


if __name__ == '__main__':
  unittest.main()
