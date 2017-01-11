# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
import webapp2
import webtest

from dashboard import stoppage_alert_debugging_info
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import stoppage_alert
from dashboard.services import milo_service

_MILO_BUILD_INFO_CURRENT = {
    'properties': {
        'got_revision_cp': 'refs/heads/master@{#345}'
    },
    'steps': {
        'sunspider': {'results': [0, ['', 'sunspider']]}
    },
}

_MILO_BUILD_INFO_NEXT = {
    'properties': {
        'got_revision_cp': 'refs/heads/master@{#370}'
    },
    'steps': {
        'sunspider': {'results': [1, ['failure', 'sunspider']]}
    },
}


class StoppageAlertDebuggingInfoHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(StoppageAlertDebuggingInfoHandlerTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/stoppage_alert_debugging_info',
        stoppage_alert_debugging_info.StoppageAlertDebuggingInfoHandler
    )])
    self.testapp = webtest.TestApp(app)

  def _AddDataToDataStore(self):
    testing_common.AddTests(['ChromiumPerf'], ['win'], {
        'sunspider': {
            'Total': {}
        }
    })
    test = utils.TestKey('ChromiumPerf/win/sunspider/Total').get()
    test_container_key = utils.GetTestContainerKey(test)
    row = graph_data.Row(id=345, buildnumber=456, parent=test_container_key)
    # Test buildbot format
    row.a_stdio_uri = ('[Buildbot stdio]('
                       'http://build.chromium.org/p/my.master.id/'
                       'builders/MyBuilder%20%281%29/builds/456/steps/'
                       'sunspider/logs/stdio)')
    row.put()
    alert = stoppage_alert.CreateStoppageAlert(test, row)
    alert.put()
    return test, row, alert

  def _CheckResults(self, results):
    self.assertEqual('345', results['current_commit_pos'])
    self.assertEqual('370', results['next_commit_pos'])
    self.assertEqual(('http://build.chromium.org/p/my.master.id/builders/'
                      'MyBuilder%20%281%29/builds/456'),
                     results['current_buildbot_status_page'])
    self.assertEqual(('http://build.chromium.org/p/my.master.id/builders/'
                      'MyBuilder%20%281%29/builds/457'),
                     results['next_buildbot_status_page'])
    self.assertEqual('ChromiumPerf/win/sunspider/Total', results['test_path'])
    self.assertEqual(('https://luci-logdog.appspot.com/v/?s=chrome%2Fbb%2F'
                      'my.master.id%2FMyBuilder__1_%2F456%2F%2B%2Frecipes%2F'
                      'steps%2Fsunspider%2F0%2Fstdout'),
                     results['current_logdog_uri'])
    self.assertEqual(('https://luci-logdog.appspot.com/v/?s=chrome%2Fbb%2F'
                      'my.master.id%2FMyBuilder__1_%2F457%2F%2B%2Frecipes%2F'
                      'steps%2Fsunspider%2F0%2Fstdout'),
                     results['next_logdog_uri'])
    self.assertEqual(0, results['current_result'][0])
    self.assertEqual('', results['current_result'][1][0])
    self.assertEqual(1, results['next_result'][0])
    self.assertEqual('failure', results['next_result'][1][0])


  def testPost_AlertKey(self):
    _, _, alert = self._AddDataToDataStore()
    milo_service.GetBuildbotBuildInfo = mock.MagicMock(
        side_effect=[_MILO_BUILD_INFO_CURRENT, _MILO_BUILD_INFO_NEXT])
    response = self.testapp.post('/stoppage_alert_debugging_info', {
        'key': alert.key.urlsafe()
    })
    info = json.loads(response.body)
    self._CheckResults(info)

  def testPost_TestPathAndRev(self):
    test, _, _ = self._AddDataToDataStore()
    milo_service.GetBuildbotBuildInfo = mock.MagicMock(
        side_effect=[_MILO_BUILD_INFO_CURRENT, _MILO_BUILD_INFO_NEXT])
    response = self.testapp.post('/stoppage_alert_debugging_info', {
        'test_path': test.test_path,
        'rev': 345,
    })
    info = json.loads(response.body)
    self._CheckResults(info)

  def testPost_NoTestPath(self):
    response = self.testapp.post('/stoppage_alert_debugging_info', {
        'rev': '345'
    })
    info = json.loads(response.body)
    self.assertEqual('No test specified', info['error'])

  def testPost_BadRev(self):
    response = self.testapp.post('/stoppage_alert_debugging_info', {
        'test_path': 'ChromiumPerf/win/sunspider/Total',
        'rev': '34324141'
    })
    info = json.loads(response.body)
    self.assertEqual('No row for alert.', info['error'])


if __name__ == '__main__':
  unittest.main()
