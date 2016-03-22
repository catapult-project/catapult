# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import stored_object
from dashboard import testing_common
from dashboard import update_test_suites
from dashboard import utils
from dashboard.models import graph_data


class ListTestSuitesTest(testing_common.TestCase):

  def setUp(self):
    super(ListTestSuitesTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/update_test_suites',
          update_test_suites.UpdateTestSuitesHandler)])
    self.testapp = webtest.TestApp(app)
    datastore_hooks.InstallHooks()
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.UnsetCurrentUser()

  def testFetchCachedTestSuites_NotEmpty(self):
    # If the cache is set, then whatever's there is returned.
    key = update_test_suites._NamespaceKey(
        update_test_suites._LIST_SUITES_CACHE_KEY)
    stored_object.Set(key, {'foo': 'bar'})
    self.assertEqual(
        {'foo': 'bar'},
        update_test_suites.FetchCachedTestSuites())

  def _AddSampleData(self):
    testing_common.AddTests(
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

  def testPost_ForcesCacheUpdate(self):
    key = update_test_suites._NamespaceKey(
        update_test_suites._LIST_SUITES_CACHE_KEY)
    stored_object.Set(key, {'foo': 'bar'})
    self.assertEqual(
        {'foo': 'bar'},
        update_test_suites.FetchCachedTestSuites())
    self._AddSampleData()
    # Because there is something cached, the cache is
    # not automatically updated when new data is added.
    self.assertEqual(
        {'foo': 'bar'},
        update_test_suites.FetchCachedTestSuites())

    # Making a request to /udate_test_suites forces an update.
    self.testapp.post('/update_test_suites')
    self.assertEqual(
        {
            'dromaeo': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'scrolling': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'really': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
        },
        update_test_suites.FetchCachedTestSuites())

  def testPost_InternalOnly(self):
    self.SetCurrentUser('internal@chromium.org')
    self._AddSampleData()
    master_key = ndb.Key('Master', 'Chromium')
    bot_key = graph_data.Bot(id='internal_mac', parent=master_key,
                             internal_only=True).put()
    graph_data.Test(id='internal_test', parent=bot_key,
                    internal_only=True).put()

    self.testapp.post('/update_test_suites?internal_only=true')

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'internal_test': {
                'mas': {'Chromium': {'internal_mac': False}},
            },
            'scrolling': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'really': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
        },
        update_test_suites.FetchCachedTestSuites())

  def testFetchCachedTestSuites_Empty_UpdatesWhenFetching(self):
    # If the cache is not set at all, then FetchCachedTestSuites
    # just updates the cache before returning the list.
    self._AddSampleData()
    self.assertEqual(
        {
            'dromaeo': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'scrolling': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
            },
            'really': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
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
                'mas': {'Chromium': {'mac': False, 'win7': False}},
                'mon': ['commit_time/www.yahoo.com'],
            },
            'scrolling': {
                'mas': {'Chromium': {'mac': False, 'win7': False}},
                'des': 'Description string.',
            },
            'really': {
                'dep': True,
                'mas': {'Chromium': {'mac': True, 'win7': True}}
            },
        },
        update_test_suites._CreateTestSuiteDict())

  def testFetchSuites(self):
    self._AddSampleData()
    suites = update_test_suites._FetchSuites()
    suite_keys = [s.key for s in suites]
    self.assertEqual(
        map(utils.TestKey, [
            'Chromium/mac/dromaeo',
            'Chromium/mac/really',
            'Chromium/mac/scrolling',
            'Chromium/win7/dromaeo',
            'Chromium/win7/really',
            'Chromium/win7/scrolling',
        ]),
        suite_keys)

  def testCreateSuiteMastersDict(self):
    self._AddSampleData()
    suites = update_test_suites._FetchSuites()
    self.assertEqual(
        {
            'dromaeo': {'Chromium': {'mac': False, 'win7': False}},
            'really': {'Chromium': {'mac': False, 'win7': False}},
            'scrolling': {'Chromium': {'mac': False, 'win7': False}},
        },
        update_test_suites._CreateSuiteMastersDict(suites))

  def testMasterToBotsToDeprecatedDict(self):
    self._AddSampleData()
    suites = [
        utils.TestKey('Chromium/mac/dromaeo').get(),
        utils.TestKey('Chromium/win7/dromaeo').get(),
    ]
    suites[0].deprecated = True
    suites[0].put()
    self.assertEqual(
        {'Chromium': {'mac': True, 'win7': False}},
        update_test_suites._MasterToBotsToDeprecatedDict(suites))

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
    suites = []
    for test_path in ['Chromium/win7/dromaeo', 'Chromium/mac/dromaeo']:
      test = utils.TestKey(test_path).get()
      test.description = 'Foo.'
      test.put()
      suites.append(test)
    self.assertEqual(
        {'dromaeo': 'Foo.'},
        update_test_suites._CreateSuiteDescriptionDict(suites))


if __name__ == '__main__':
  unittest.main()
