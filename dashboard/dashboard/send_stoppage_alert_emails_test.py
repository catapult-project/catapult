# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import send_stoppage_alert_emails
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


class EmailSummaryTest(testing_common.TestCase):

  def setUp(self):
    super(EmailSummaryTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/send_stoppage_alert_emails',
          send_stoppage_alert_emails.SendStoppageAlertEmailsHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddSampleData(self):
    """Puts a TestMetadata and Row in the datastore and returns the entities."""
    testing_common.AddTests(
        ['M'], ['b'], {'suite': {'foo': {}, 'bar': {}, 'baz': {}}})
    sheriff.Sheriff(
        email='foo@chromium.org', id='Foo', patterns=['*/*/*/*'],
        stoppage_alert_delay=3).put()
    stdio_dict = {
        'foo': {'a_stdio_uri': '[Buildbot stdio](http://build.chromium.org/p/'
                               'chromium.perf/builders/Mac/builds/187/steps/'
                               'media.mse_cases/logs/stdio)'},
        'bar': {'a_a_stdio_uri': '[Buildbot stdio](http://build.chromium.org/p/'
                                 'chromium.perf/builders/Win/builds/184/steps/'
                                 'media.mse_cases/logs/stdio)'},
        'baz': {'value': 1000},
    }
    for name in ('foo', 'bar', 'baz'):
      test_path = 'M/b/suite/%s' % name
      testing_common.AddRows(test_path, {100: stdio_dict[name]})

  def testGet_ThreeAlertsOneSheriff_EmailSent(self):
    self._AddSampleData()
    for name in ('foo', 'bar', 'baz'):
      test = utils.TestKey('M/b/suite/%s' % name).get()
      row = graph_data.Row.query(
          graph_data.Row.parent_test == utils.OldStyleTestKey(test.key)).get()
      stoppage_alert.CreateStoppageAlert(test, row).put()
    self.testapp.get('/send_stoppage_alert_emails')
    messages = self.mail_stub.get_sent_messages()
    self.assertEqual(1, len(messages))
    self.assertEqual('gasper-alerts@google.com', messages[0].sender)
    self.assertEqual('foo@chromium.org', messages[0].to)
    self.assertIn('3', messages[0].subject)
    body = str(messages[0].body)
    self.assertIn('foo', body)
    self.assertIn('bar', body)
    self.assertIn('baz', body)
    self.assertIn(
        'http://build.chromium.org/p/chromium.perf/builders/Mac/builds/187',
        body)
    self.assertIn(
        'http://build.chromium.org/p/chromium.perf/builders/Win/builds/184',
        body)
    self.assertIn(
        'https://luci-logdog.appspot.com/v/?s=chrome%2Fbb%2Fchromium.perf%2F'
        'Win%2F184%2F%2B%2Frecipes%2Fsteps%2Fmedia.mse_cases%2F0%2Fstdout',
        body)
    stoppage_alerts = stoppage_alert.StoppageAlert.query().fetch()
    for alert in stoppage_alerts:
      self.assertTrue(alert.mail_sent)

  def testGet_NoAlerts_EmailSent(self):
    self.testapp.get('/send_stoppage_alert_emails')
    messages = self.mail_stub.get_sent_messages()
    self.assertEqual(0, len(messages))


if __name__ == '__main__':
  unittest.main()
