# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import webapp2
import webtest

from dashboard import cron_update_sheriff
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly_config
from dashboard.models import sheriff as sheriff_module


_TESTS = [
    ['ChromiumPerf'],
    ['mac'],
    {
        'SunSpider': {
            'Total': {
                't': {},
                't_ref': {},
            },
        },
        'OtherTest': {
            'OtherMetric': {
                'foo1': {},
                'foo2': {},
            },
        },
    }
]


class CronSheriffUpdateTest(testing_common.TestCase):

  def setUp(self):
    super(CronSheriffUpdateTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/cron/update_sheriff', cron_update_sheriff.CronUpdateSheriffHandler)])
    self.testapp = webtest.TestApp(app)
    cron_update_sheriff._TESTS_PER_QUERY = 1

  def testPost_UpdatesSheriff(self):
    testing_common.AddTests(*_TESTS)

    sheriff_module.Sheriff(
        id='s1', email='a@chromium.org', patterns=[
            '*/*/SunSpider/Total']).put()

    t = utils.TestKey('ChromiumPerf/mac/SunSpider/Total').get()
    self.assertIsNone(t.sheriff)
    self.assertIsNone(t.overridden_anomaly_config)

    self.testapp.post('/cron/update_sheriff')
    self.ExecuteDeferredTasks(cron_update_sheriff._TASK_QUEUE_NAME)

    t = utils.TestKey('ChromiumPerf/mac/SunSpider/Total').get()
    self.assertIsNotNone(t.sheriff)
    self.assertIsNone(t.overridden_anomaly_config)

  def testPost_UpdatesAnomalyConfig(self):
    testing_common.AddTests(*_TESTS)

    anomaly_config.AnomalyConfig(
        id='anomaly_config1', config='',
        patterns=['ChromiumPerf/mac/SunSpider/Total']).put()

    t = utils.TestKey('ChromiumPerf/mac/SunSpider/Total').get()
    self.assertIsNone(t.sheriff)
    self.assertIsNone(t.overridden_anomaly_config)

    self.testapp.post('/cron/update_sheriff')
    self.ExecuteDeferredTasks(cron_update_sheriff._TASK_QUEUE_NAME)

    t = utils.TestKey('ChromiumPerf/mac/SunSpider/Total').get()
    self.assertIsNone(t.sheriff)
    self.assertIsNotNone(t.overridden_anomaly_config)
