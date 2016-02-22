# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import webapp2
import webtest

from dashboard import get_logs
from dashboard import quick_logger
from dashboard import testing_common


class GetLogsTest(testing_common.TestCase):

  def setUp(self):
    super(GetLogsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/get_logs', get_logs.GetLogsHandler)])
    self.testapp = webtest.TestApp(app)

  def testPost_WithTimestamp_RespondsWithNewLogs(self):
    logger = quick_logger.QuickLogger('test_namespace', 'test_name')
    logger.Log('First message.')
    logger.Log('Second message.')
    # Set back the time on these records.
    logger._records[0].timestamp -= 1
    logger._records[1].timestamp -= 2
    logger.Save()
    response = self.testapp.post('/get_logs', {
        'namespace': 'test_namespace',
        'name': 'test_name',
        'size': 100
    })
    response_logs = json.loads(response.body)
    self.assertEqual(2, len(response_logs))

    logger.Log('Third message.')
    logger.Save()

    response = self.testapp.post('/get_logs', {
        'namespace': 'test_namespace',
        'name': 'test_name',
        'size': 100,
        'after_timestamp': repr(response_logs[0]['timestamp'])
    })

    response_logs = json.loads(response.body)
    self.assertEqual(1, len(response_logs))
    self.assertEqual('Third message.', response_logs[0]['message'])
