# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for shrink_timestamp_revisions module."""

import unittest

import webapp2
import webtest

from dashboard import shrink_timestamp_revisions
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data


class ShrinkTimestampRevisionsTest(testing_common.TestCase):

  def setUp(self):
    super(ShrinkTimestampRevisionsTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/shrink_timestamp_revisions',
          shrink_timestamp_revisions.ShrinkTimestampRevisionsHandler)])
    self.testapp = webtest.TestApp(app)

  def testConvertTimestamp(self):
    convert = shrink_timestamp_revisions._ConvertTimestamp
    self.assertEqual(-5139, convert(1320001000))  # Before 2013
    self.assertEqual(417, convert(1360001000))  # In Feb 2013
    self.assertEqual(5972, convert(1400001000))  # In 2014
    self.assertEqual(5972, convert(1400001010))  # 10 seconds later
    self.assertEqual(12917, convert(1450001010))  # In 2015
    self.assertEqual(19861, convert(1500001010))  # In 2017

  def testPost_NoParameters_ReportsError(self):
    response = self.testapp.post('/shrink_timestamp_revisions', status=500)
    self.assertEqual('Missing ancestor parameter.\n', response.body)

  def testGet_SameAsPost(self):
    response1 = self.testapp.get('/shrink_timestamp_revisions', status=500)
    response2 = self.testapp.post('/shrink_timestamp_revisions', status=500)
    self.assertEqual(response1.body, response2.body)

  def testPost_WithAncestor_AllRowsMoved(self):
    testing_common.AddTests(
        ['M'], ['b1', 'b2'], {'foo': {'bar': {}, 'baz': {}}})
    for test_path in ('M/b1/foo/bar', 'M/b1/foo/baz', 'M/b2/foo/bar'):
      # range(1425001000, 1430001000, 6000) includes 834 numbers.
      testing_common.AddRows(
          test_path,
          {i for i in range(1425001000, 1430001000, 6000)})

    self.testapp.post(
        '/shrink_timestamp_revisions', {'ancestor': 'M/b1'})
    self.ExecuteTaskQueueTasks(
        '/shrink_timestamp_revisions', shrink_timestamp_revisions._QUEUE_NAME)

    b1_bar_rows = graph_data.Row.query(
        graph_data.Row.parent_test == utils.TestKey('M/b1/foo/bar')).fetch()
    b1_baz_rows = graph_data.Row.query(
        graph_data.Row.parent_test == utils.TestKey('M/b1/foo/baz')).fetch()
    b2_bar_rows = graph_data.Row.query(
        graph_data.Row.parent_test == utils.TestKey('M/b2/foo/bar')).fetch()
    self.assertGreater(len(b1_bar_rows), 600)
    self.assertGreater(len(b1_baz_rows), 600)
    self.assertEqual(834, len(b2_bar_rows))
    for r in b1_bar_rows:
      self.assertLess(r.revision, 300000)
    for r in b1_baz_rows:
      self.assertLess(r.revision, 300000)
    for r in b2_bar_rows:
      self.assertGreater(r.revision, 300000)

  def testGet_WithAncestor_AllAlertsUpdated(self):
    testing_common.AddTests(
        ['M'], ['b1', 'b2'], {'foo': {'bar': {}, 'baz': {}}})
    testing_common.AddRows(
        'M/b1/foo/bar',
        {i for i in range(1431001000, 1432001000, 6000)})
    test_key = utils.TestKey('M/b1/foo/bar')
    # range(1431001000, 1431081000, 6000) includes 14 numbers.
    for i in range(1431001000, 1431081000, 6000):
      anomaly.Anomaly(
          start_revision=i, end_revision=i+12000, test=test_key,
          median_before_anomaly=100, median_after_anomaly=200).put()

    self.testapp.post(
        '/shrink_timestamp_revisions', {'ancestor': 'M'})
    self.ExecuteTaskQueueTasks(
        '/shrink_timestamp_revisions', shrink_timestamp_revisions._QUEUE_NAME)

    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(14, len(anomalies))
    for a in anomalies:
      self.assertLess(a.start_revision, 300000)
      self.assertLess(a.end_revision, 300000)


if __name__ == '__main__':
  unittest.main()
