# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for update_test_suites module."""

import unittest

import webapp2
import webtest

from dashboard import testing_common
from dashboard import update_test_suites
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import multipart_entity


class ListTestSuitesTest(testing_common.TestCase):

  def setUp(self):
    super(ListTestSuitesTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/update_test_suites',
          update_test_suites.UpdateTestSuitesHandler)])
    self.testapp = webtest.TestApp(app)

  def testFetchCachedTestSuites_NotEmpty(self):
    # If the cache is set, then whatever's there is returned.
    key = update_test_suites._NamespaceKey(graph_data.LIST_SUITES_CACHE_KEY)
    multipart_entity.Set(key, {'foo': 'bar'})
    self.assertEqual(
        {'foo': 'bar'},
        update_test_suites.FetchCachedTestSuites())

  def testFetchCachedTestSuites_Empty_ReturnsNone(self):
    # If the cache is not set, then FetchCachedTestSuites
    # just returns None; compiling the list of test suites would
    # take too long.
    self._AddSampleData()
    self.assertIsNone(update_test_suites.FetchCachedTestSuites())

  def _AddSampleData(self):
    testing_common.AddDataToMockDataStore(
        ['Chromium'],
        ['win7', 'mac'],
        {
            'dromaeo': {
                'dom': {},
                'jslib': {},
            },
            'scrolling': {
                'commit_time': {
                    'www.yahoo.com': {},
                    'www.cnn.com': {},
                },
                'commit_time_ref': {},
            },
            'really': {
                'nested': {
                    'very': {
                        'deeply': {
                            'subtest': {}
                        }
                    },
                    'very_very': {}
                }
            },
        })

  def testPost(self):
    self._AddSampleData()
    # The cache starts out empty.
    self.assertIsNone(update_test_suites.FetchCachedTestSuites())
    self.testapp.post('/update_test_suites')
    # After the request is made, it will no longer be empty.
    self.assertEqual(
        {
            'dromaeo': {
                'masters': {'Chromium': ['mac', 'win7']},
                'monitored': [],
                'description': '',
                'deprecated': False,
            },
            'scrolling': {
                'masters': {'Chromium': ['mac', 'win7']},
                'monitored': [],
                'description': '',
                'deprecated': False,
            },
            'really': {
                'masters': {'Chromium': ['mac', 'win7']},
                'monitored': [],
                'description': '',
                'deprecated': False,
            },
        },
        update_test_suites.FetchCachedTestSuites())

  def testCreateTestSuitesDict(self):
    self._AddSampleData()

    # For one test suite, add a monitored test and set the suite as deprecated.
    # Only set it as deprecated on one of two bots; this test suite should not
    # be marked as deprecated in the response dict, but only the non-deprecated
    # bot (mac in the this sample data) should be listed.
    test = utils.TestKey('Chromium/win7/dromaeo').get()
    test.monitored = [utils.TestKey(
        'Chromium/win7/dromaeo/commit_time/www.yahoo.com')]
    test.put()

    # For another test suite, set it as deprecated on both bots -- it should
    # be marked as deprecated in the response dict.
    for bot in ['win7', 'mac']:
      test = utils.TestKey('Chromium/%s/really' % bot).get()
      test.deprecated = True
      test.put()

    # Set the description string for two test suites on both bots. It doesn't
    # matter whether this description is set for both bots or just one.
    for test_path in ['Chromium/win7/scrolling', 'Chromium/mac/scrolling']:
      test = utils.TestKey(test_path).get()
      test.description = 'Description string.'
      test.put()

    self.assertEqual(
        {
            'dromaeo': {
                'masters': {'Chromium': ['mac', 'win7']},
                'monitored': ['commit_time/www.yahoo.com'],
                'description': '',
                'deprecated': False,
            },
            'scrolling': {
                'masters': {'Chromium': ['mac', 'win7']},
                'monitored': [],
                'description': 'Description string.',
                'deprecated': False,
            },
        },
        update_test_suites._CreateTestSuiteDict())

  def testFetchTestSuiteKeys(self):
    self._AddSampleData()
    self.assertEqual(
        map(utils.TestKey, [
            'Chromium/mac/dromaeo',
            'Chromium/mac/really',
            'Chromium/mac/scrolling',
            'Chromium/win7/dromaeo',
            'Chromium/win7/really',
            'Chromium/win7/scrolling',
        ]),
        update_test_suites._FetchTestSuiteKeys())

  def testCreateSuiteMastersDict(self):
    self._AddSampleData()
    suite_keys = update_test_suites._FetchTestSuiteKeys()
    self.assertEqual(
        {
            'dromaeo': {'Chromium': ['mac', 'win7']},
            'really': {'Chromium': ['mac', 'win7']},
            'scrolling': {'Chromium': ['mac', 'win7']},
        },
        update_test_suites._CreateSuiteMastersDict(suite_keys))

  def testMasterToBotsDict(self):
    self._AddSampleData()
    keys = map(utils.TestKey, [
        'Chromium/mac/suite',
        'Chromium/win7/suite',
    ])
    self.assertEqual(
        {'Chromium': ['mac', 'win7']},
        update_test_suites._MasterToBotsDict(keys))

  def testCreateSuiteMonitoredDict(self):
    self._AddSampleData()
    test_win = utils.TestKey('Chromium/win7/dromaeo').get()
    test_win.monitored = [utils.TestKey(
        'Chromium/win7/dromaeo/commit_time/www.yahoo.com')]
    test_win.put()
    test_mac = utils.TestKey('Chromium/mac/dromaeo').get()
    test_mac.monitored = [utils.TestKey(
        'Chromium/mac/dromaeo/commit_time/www.cnn.com')]
    test_mac.put()
    self.assertEqual(
        {
            'dromaeo': [
                'commit_time/www.cnn.com',
                'commit_time/www.yahoo.com',
            ]
        },
        update_test_suites._CreateSuiteMonitoredDict())

  def testGetSubTestPath(self):
    key = utils.TestKey('Chromium/mac/my_suite/foo/bar')
    self.assertEqual('foo/bar', update_test_suites._GetTestSubPath(key))

  def testCreateSuiteDescriptionDict(self):
    self._AddSampleData()
    for test_path in ['Chromium/win7/dromaeo', 'Chromium/mac/dromaeo']:
      test = utils.TestKey(test_path).get()
      test.description = 'Foo.'
      test.put()
    suite_keys = update_test_suites._FetchTestSuiteKeys()
    self.assertEqual(
        {'dromaeo': 'Foo.', 'scrolling': '', 'really': ''},
        update_test_suites._CreateSuiteDescriptionDict(suite_keys))


if __name__ == '__main__':
  unittest.main()
