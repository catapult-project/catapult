# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import speed_releasing
from dashboard.common import datastore_hooks
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import table_config
from dashboard.models import graph_data

_SAMPLE_BOTS = ['ChromiumPerf/win', 'ChromiumPerf/linux']
_DOWNSTREAM_BOTS = ['ClankInternal/win', 'ClankInternal/linux']
_SAMPLE_TESTS = ['my_test_suite/my_test', 'my_test_suite/my_other_test']
_SAMPLE_LAYOUT = ('{ "my_test_suite/my_test": ["Foreground", '
                  '"Pretty Name 1"],"my_test_suite/my_other_test": '
                  ' ["Foreground", "Pretty Name 2"]}')

class SpeedReleasingTest(testing_common.TestCase):

  def setUp(self):
    super(SpeedReleasingTest, self).setUp()
    app = webapp2.WSGIApplication([(
        r'/speed_releasing/(.*)',
        speed_releasing.SpeedReleasingHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetSheriffDomains(['chromium.org'])
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.SetCurrentUser('internal@chromium.org', is_admin=True)

  def tearDown(self):
    super(SpeedReleasingTest, self).tearDown()
    self.UnsetCurrentUser()

  def _AddInternalBotsToDataStore(self):
    """Adds sample bot/master pairs."""
    master_key = ndb.Key('Master', 'ChromiumPerf')
    graph_data.Bot(
        id='win', parent=master_key, internal_only=True).put()
    graph_data.Bot(
        id='linux', parent=master_key, internal_only=True).put()

  def _AddPublicBotsToDataStore(self):
    """Adds sample bot/master pairs."""
    master_key = ndb.Key('Master', 'ChromiumPerf')
    graph_data.Bot(
        id='win', parent=master_key, internal_only=False).put()
    graph_data.Bot(
        id='linux', parent=master_key, internal_only=False).put()

  def _AddTableConfigDataStore(self, name, is_internal, is_downstream=False):
    """Add sample internal only tableConfig."""
    keys = self._AddTests(is_downstream)
    if is_internal:
      self._AddInternalBotsToDataStore()
    else:
      self._AddPublicBotsToDataStore()
    table_config.CreateTableConfig(
        name=name, bots=_SAMPLE_BOTS if not is_downstream else _DOWNSTREAM_BOTS,
        tests=_SAMPLE_TESTS,
        layout=_SAMPLE_LAYOUT,
        username='internal@chromium.org')
    return keys

  def _AddTests(self, is_downstream):
    master = 'ClankInternal' if is_downstream else 'ChromiumPerf'
    testing_common.AddTests([master], ['win', 'linux'], {
        'my_test_suite': {
            'my_test': {},
            'my_other_test': {},
        }
    })
    keys = [
        utils.TestKey(master + '/win/my_test_suite/my_test'),
        utils.TestKey(master + '/win/my_test_suite/my_other_test'),
        utils.TestKey(master + '/linux/my_test_suite/my_test'),
        utils.TestKey(master + '/linux/my_test_suite/my_other_test'),
    ]
    for test_key in keys:
      test = test_key.get()
      test.units = 'timeDurationInMs'
      test.put()
    return keys

  def _AddRows(self, keys):
    for key in keys:
      testing_common.AddRows(utils.TestPath(key), [1, 2, 3, 445588])

  def _AddDownstreamRows(self, keys):
    revisions = [1, 2, 1485025126, 1485099999]
    for key in keys:
      testing_common.AddRows(
          utils.TestPath(key), revisions)
    for key in keys:
      for rev in revisions:
        row_key = utils.GetRowKey(key, rev)
        row = row_key.get()
        row.r_commit_pos = str(rev / 10000)
        row.a_default_rev = 'r_foo'
        row.r_foo = 'abcdefghijk'
        row.put()

  def testGet_ShowPage(self):
    response = self.testapp.get('/speed_releasing/')
    self.assertIn('speed-releasing-page', response)

  def testPost_InternalListPage(self):
    self._AddTableConfigDataStore('BestTable', True)
    self._AddTableConfigDataStore('SecondBestTable', True)
    self._AddTableConfigDataStore('ThirdBestTable', False)
    response = self.testapp.post('/speed_releasing/')
    self.assertIn('"show_list": true', response)
    self.assertIn('"list": ["BestTable", "SecondBestTable", '
                  '"ThirdBestTable"]', response)

  def testPost_ShowInternalTable(self):
    keys = self._AddTableConfigDataStore('BestTable', True)
    self._AddRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?revA=1&revB=2')
    self.assertIn('"name": "BestTable"', response)
    self.assertIn('"table_bots": ["ChromiumPerf/win", '
                  '"ChromiumPerf/linux"]', response)
    self.assertIn('"table_tests": ["my_test_suite/my_test",'
                  ' "my_test_suite/my_other_test"]', response)
    self.assertIn('"table_layout"', response)
    self.assertIn('"revisions": [2, 1]', response)
    self.assertIn('"display_revisions": [2, 1]', response)
    self.assertIn('"units": {"my_test_suite/my_test": "timeDurationInMs", '
                  '"my_test_suite/my_other_test": "timeDurationInMs"',
                  response)
    self.assertIn('"categories": {"Foreground": 2}', response)
    self.assertIn('"values": {"1": {"ChromiumPerf/linux": '
                  '{"my_test_suite/my_test": 1.0, '
                  '"my_test_suite/my_other_test": 1.0}, '
                  '"ChromiumPerf/win": {"my_test_suite/my_test": 1.0, '
                  '"my_test_suite/my_other_test": 1.0}}, '
                  '"2": {"ChromiumPerf/linux": {"my_test_suite/my_test": '
                  '2.0, "my_test_suite/my_other_test": 2.0}, '
                  '"ChromiumPerf/win": {"my_test_suite/my_test": 2.0, '
                  '"my_test_suite/my_other_test": 2.0}}}', response)

  def testPost_InternalListPageToExternalUser(self):
    self._AddTableConfigDataStore('BestTable', True)
    self._AddTableConfigDataStore('SecondBestTable', True)
    self._AddTableConfigDataStore('ThirdBestTable', False)
    self.UnsetCurrentUser()
    datastore_hooks.InstallHooks()
    response = self.testapp.post('/speed_releasing/')
    self.assertIn('"show_list": true', response)
    self.assertIn('"list": ["ThirdBestTable"]', response)

  def testPost_ShowInternalTableToExternalUser(self):
    self._AddTableConfigDataStore('BestTable', True)
    self.UnsetCurrentUser()
    self.testapp.post('/speed_releasing/BestTable?revA=1&revB=2', {
    }, status=500) # 500 means user can't see data.

  def testPost_TableWithNoRevParams(self):
    self._AddTableConfigDataStore('BestTable', True)
    response = self.testapp.post('/speed_releasing/BestTable')
    self.assertIn('Invalid revisions.', response)

  def testPost_TableWithTableNameThatDoesntExist(self):
    response = self.testapp.post('/speed_releasing/BestTable')
    self.assertIn('Invalid table name.', response)

  def testPost_TableWithNoRevParamsOnlyDownStream(self):
    keys = self._AddTableConfigDataStore('BestTable', True, True)
    self._AddDownstreamRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?revA=1485099999&'
                                 'revB=1485025126')
    self.assertIn('"revisions": [1485099999, 1485025126]', response)
    self.assertIn('"display_revisions": ["148509-abc", "148502-abc"]', response)

  def testPost_TableWithMilestoneParam(self):
    keys = self._AddTableConfigDataStore('BestTable', True)
    self._AddRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?m=56')
    self.assertIn('"revisions": [445288, 433400]', response)

  def testPost_TableWithNewestMilestoneParam(self):
    keys = self._AddTableConfigDataStore('BestTable', True)
    self._AddRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?m=57')
    self.assertIn('"revisions": [445588, 445288]', response)

  def testPost_TableWithHighMilestoneParam(self):
    keys = self._AddTableConfigDataStore('BestTable', True)
    self._AddRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?m=71')
    self.assertIn('"error": "No data for that milestone."', response)

  def testPost_TableWithLowMilestoneParam(self):
    keys = self._AddTableConfigDataStore('BestTable', True)
    self._AddRows(keys)
    response = self.testapp.post('/speed_releasing/BestTable?m=7')
    self.assertIn('"error": "No data for that milestone."', response)

