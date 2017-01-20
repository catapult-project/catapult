# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import speed_releasing
from dashboard.common import datastore_hooks
from dashboard.common import testing_common
from dashboard.models import table_config
from dashboard.models import graph_data

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

  def _AddTableConfigDataStore(self, name, is_internal):
    """Add sample internal only tableConfig."""
    if is_internal:
      self._AddInternalBotsToDataStore()
    else:
      self._AddPublicBotsToDataStore()
    table_config.CreateTableConfig(
        name=name, bots=['ChromiumPerf/win', 'ChromiumPerf/linux'],
        tests=['my_test_suite/my_test', 'my_test_suite/my_other_test'],
        layout='{ "system_health.memory_mobile/foreground/ashmem":'
               '["Foreground", "Ashmem"]}',
        username='internal@chromium.org')

  def testGet_ShowPage(self):
    response = self.testapp.get('/speed_releasing/')
    self.assertIn('speed-releasing-page', response)

  def testPost_InternalListPage(self):
    self._AddTableConfigDataStore('BestTable', True)
    self._AddTableConfigDataStore('SecondBestTable', True)
    self._AddTableConfigDataStore('ThirdBestTable', False)
    response = self.testapp.post('/speed_releasing/')
    self.assertIn('\"show_list\": true', response)
    self.assertIn('\"list\": ["BestTable", "SecondBestTable", '
                  '"ThirdBestTable"]', response)

  def testPost_ShowInternalTable(self):
    self._AddTableConfigDataStore('BestTable', True)
    response = self.testapp.post('/speed_releasing/BestTable')
    self.assertIn('\"name\": "BestTable"', response)
    self.assertIn('\"table_bots\": [\"ChromiumPerf/win", '
                  '"ChromiumPerf/linux\"]', response)
    self.assertIn('\"table_tests\": [\"my_test_suite/my_test",'
                  ' "my_test_suite/my_other_test\"]', response)
    self.assertIn('\"table_layout\"', response)

  def testPost_InternalListPageToExternalUser(self):
    self._AddTableConfigDataStore('BestTable', True)
    self._AddTableConfigDataStore('SecondBestTable', True)
    self._AddTableConfigDataStore('ThirdBestTable', False)
    self.UnsetCurrentUser()
    datastore_hooks.InstallHooks()
    response = self.testapp.post('/speed_releasing/')
    self.assertIn('\"show_list\": true', response)
    self.assertIn('\"list\": ["ThirdBestTable"]', response)

  def testPost_ShowInternalTableToExternalUser(self):
    self._AddTableConfigDataStore('BestTable', True)
    self.UnsetCurrentUser()
    self.testapp.post('/speed_releasing/BestTable', {
    }, status=500) # 500 means user can't see data.
