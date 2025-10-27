# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from flask import Flask
import unittest
import webtest

from google.appengine.ext import ndb

from dashboard import update_test_suites
from dashboard.common import descriptor
from dashboard.common import namespaced_stored_object
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import graph_data
from unittest import mock

flask_app = Flask(__name__)


@flask_app.route('/update_test_suites', methods=['GET', 'POST'])
def UpdateTestSuitesPost():
  return update_test_suites.UpdateTestSuitesPost()


class ListTestSuitesTest(testing_common.TestCase):

  def setUp(self):
    super().setUp()
    self.testapp = webtest.TestApp(flask_app)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.UnsetCurrentUser()
    stored_object.Set(descriptor.PARTIAL_TEST_SUITES_KEY, [
        'TEST_PARTIAL_TEST_SUITE',
    ])
    stored_object.Set(descriptor.GROUPABLE_TEST_SUITE_PREFIXES_KEY, [
        'TEST_GROUPABLE%',
    ])
    descriptor.Descriptor.ResetMemoizedConfigurationForTesting()

  def testFetchCachedTestSuites_NotEmpty(self):
    # If the cache is set, then whatever's there is returned.
    key = namespaced_stored_object.NamespaceKey(
        update_test_suites._LIST_SUITES_CACHE_KEY)
    stored_object.Set(key, {'foo': 'bar'})
    self.assertEqual({'foo': 'bar'}, update_test_suites.FetchCachedTestSuites())

  def _AddSampleData(self):
    testing_common.AddTests(
        ['Chromium'], ['win7', 'mac'], {
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
    key = namespaced_stored_object.NamespaceKey(
        update_test_suites._LIST_SUITES_CACHE_KEY)
    stored_object.Set(key, {'foo': 'bar'})
    self.assertEqual({'foo': 'bar'}, update_test_suites.FetchCachedTestSuites())
    self._AddSampleData()
    # Because there is something cached, the cache is
    # not automatically updated when new data is added.
    self.assertEqual({'foo': 'bar'}, update_test_suites.FetchCachedTestSuites())

    stored_object.Set(
        namespaced_stored_object.NamespaceKey(
            update_test_suites.TEST_SUITES_2_CACHE_KEY), ['foo'])
    self.assertEqual(['foo'], update_test_suites.FetchCachedTestSuites2())

    self.testapp.post('/update_test_suites')

    self.ExecuteDeferredTasks('default')

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites.FetchCachedTestSuites())

    self.assertEqual(['dromaeo', 'really', 'scrolling'],
                     update_test_suites.FetchCachedTestSuites2())

  def testPost_InternalOnly(self):
    self.SetCurrentUser('internal@chromium.org')
    self._AddSampleData()
    master_key = ndb.Key('Master', 'Chromium')
    graph_data.Bot(
        id='internal_mac', parent=master_key, internal_only=True).put()
    t = graph_data.TestMetadata(
        id='Chromium/internal_mac/internal_test', internal_only=True)
    t.UpdateSheriff()
    t.put()

    self.testapp.post('/update_test_suites?internal_only=true')

    self.ExecuteDeferredTasks('default')

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'internal_test': {
                'mas': {
                    'Chromium': {
                        'internal_mac': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_BasicDescription(self):
    self._AddSampleData()

    for test_path in ['Chromium/win7/scrolling', 'Chromium/mac/scrolling']:
      test = utils.TestKey(test_path).get()
      test.description = 'Description string.'
      test.UpdateSheriff()
      test.put()

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'des': 'Description string.',
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_DifferentMasters(self):
    # If the cache is not set at all, then FetchCachedTestSuites
    # just updates the cache before returning the list.
    self._AddSampleData()
    testing_common.AddTests(['ChromiumFYI'], ['linux'], {
        'sunspider': {
            'Total': {},
        },
    })
    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'sunspider': {
                'mas': {
                    'ChromiumFYI': {
                        'linux': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_SingleDeprecatedBot(self):
    self._AddSampleData()

    # For another test suite, set it as deprecated on both bots -- it should
    # be marked as deprecated in the response dict.
    for bot in ['win7']:
      test = utils.TestKey('Chromium/%s/really' % bot).get()
      test.deprecated = True
      test.UpdateSheriff()
      test.put()

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': True
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_AllDeprecatedBots(self):
    self._AddSampleData()

    # For another test suite, set it as deprecated on both bots -- it should
    # be marked as deprecated in the response dict.
    for bot in ['win7', 'mac']:
      test = utils.TestKey('Chromium/%s/really' % bot).get()
      test.deprecated = True
      test.UpdateSheriff()
      test.put()

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': True,
                        'win7': True
                    }
                },
                'dep': True,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_BasicMonitored(self):
    self._AddSampleData()

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites_MultipleMonitored(self):
    self._AddSampleData()
    testing_common.AddTests(['ChromiumFYI'], ['linux'], {
        'dromaeo': {
            'foo': {},
        },
    })

    self.assertEqual(
        {
            'dromaeo': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    },
                    'ChromiumFYI': {
                        'linux': False
                    }
                },
                'dep': False,
            },
            'scrolling': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
            'really': {
                'mas': {
                    'Chromium': {
                        'mac': False,
                        'win7': False
                    }
                },
                'dep': False,
            },
        }, update_test_suites._CreateTestSuiteDict())

  def testFetchSuites(self):
    self._AddSampleData()
    suites = update_test_suites._FetchSuites()
    suite_keys = [s.key for s in suites]
    self.assertEqual(
        list(
            map(utils.TestKey, [
                'Chromium/mac/dromaeo',
                'Chromium/mac/really',
                'Chromium/mac/scrolling',
                'Chromium/win7/dromaeo',
                'Chromium/win7/really',
                'Chromium/win7/scrolling',
            ])), suite_keys)


  def testPartialTestSuites(self):
    testing_common.AddTests(['master'], ['bot'], {
        'TEST_PARTIAL_TEST_SUITE': {
            'COMPOSITE': {
                'measurement': {},
            },
        },
    })
    self.testapp.post('/update_test_suites')

    self.ExecuteDeferredTasks('default')

    self.assertEqual(['TEST_PARTIAL_TEST_SUITE:COMPOSITE'],
                     update_test_suites.FetchCachedTestSuites2())

  @mock.patch(
      'dashboard.update_test_suites.descriptor.Descriptor.FromTestPathAsync')
  @mock.patch('google.appengine.ext.ndb.Query.fetch_page_async')
  def testListTestSuites_Paging(self, mock_fetch_page, mock_from_path):
    # This test ensures that the paging logic in _ListTestSuitesAsync
    # correctly loops and aggregates results from multiple pages.

    # --- 1. Setup Mocks ---

    # We will simulate two pages of results.
    mock_key_1 = ndb.Key('TestMetadata', 'M/b/suite1')
    mock_key_2 = ndb.Key('TestMetadata', 'M/b/suite2')
    mock_cursor_obj = ndb.Cursor()

    # Configure fetch_page_async to be called twice.
    # Each call must return a Future that resolves to the page data.
    future_page1 = ndb.Future()
    future_page1.set_result(
        ([mock_key_1], mock_cursor_obj, True))  # Set result immediately

    future_page2 = ndb.Future()
    future_page2.set_result(
        ([mock_key_2], None, False))  # Set result immediately

    mock_fetch_page.side_effect = [
        future_page1,
        future_page2,
    ]

    # Mock the descriptors that will be looked up.
    # We must return Futures because the code yields them.
    mock_desc_1 = mock.Mock()
    mock_desc_1.test_suite = 'suite1'
    future1 = ndb.Future()
    future1.set_result(mock_desc_1)

    mock_desc_2 = mock.Mock()
    mock_desc_2.test_suite = 'suite2'
    future2 = ndb.Future()
    future2.set_result(mock_desc_2)

    mock_from_path.side_effect = [future1, future2]

    # --- 2. Run the Function ---
    # We call the synchronous wrapper, which will run our
    # modified _ListTestSuitesAsync.
    result = update_test_suites._ListTestSuites()

    # --- 3. Assertions ---

    # Check that the final list is correct and aggregated
    self.assertEqual(['suite1', 'suite2'], result)

    # Check that fetch_page_async was called twice.
    self.assertEqual(2, mock_fetch_page.call_count)

    # Check that the first call had no cursor
    calls = mock_fetch_page.call_args_list
    self.assertEqual(None, calls[0][1]['start_cursor'])

    # Check that the second call used the cursor from the first
    self.assertEqual(mock_cursor_obj, calls[1][1]['start_cursor'])

if __name__ == '__main__':
  unittest.main()
