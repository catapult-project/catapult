# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for sheriff module."""

import unittest

from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


class StoppageAlertTest(testing_common.TestCase):

  def _AddSampleData(self):
    """Puts a Test and Row in the datastore and returns the entities."""
    testing_common.AddTests(['M'], ['b'], {'suite': {'foo': {}}})
    sheriff.Sheriff(id='Foo', patterns=['*/*/*/*']).put()
    test_path = 'M/b/suite/foo'
    test_key = utils.TestKey(test_path)
    test = test_key.get()
    testing_common.AddRows(test_path, {100})
    row = graph_data.Row.query().get()
    return test, row

  def testCreateStoppageAlert_Basic(self):
    test, row = self._AddSampleData()
    alert = stoppage_alert.CreateStoppageAlert(test, row)
    alert.put()
    self.assertFalse(alert.internal_only)
    self.assertEqual(test.sheriff, alert.sheriff)
    self.assertEqual(test.key, alert.test)
    self.assertEqual(row.revision, alert.revision)
    self.assertEqual(row.revision, alert.start_revision)
    self.assertEqual(row.revision, alert.end_revision)
    self.assertFalse(alert.mail_sent)
    self.assertIsNone(alert.bug_id)
    self.assertIsNotNone(alert.timestamp)

  def testCreateStoppageAlert_InternalOnly(self):
    test, row = self._AddSampleData()
    test.internal_only = True
    test.put()
    alert = stoppage_alert.CreateStoppageAlert(test, row)
    self.assertTrue(alert.internal_only)

  def testPutMultipleTimes_OnlyOneEntityPut(self):
    test, row = self._AddSampleData()
    stoppage_alert.CreateStoppageAlert(test, row).put()
    stoppage_alert.CreateStoppageAlert(test, row).put()
    self.assertEqual(1, len(stoppage_alert.StoppageAlert.query().fetch()))

  def testGetStoppageAlert_NoEntity_ReturnsNone(self):
    self.assertIsNone(stoppage_alert.GetStoppageAlert('M/b/suite/bar', 123))

  def testGetStoppageAlert_EntityExists_ReturnsEntity(self):
    test, row = self._AddSampleData()
    stoppage_alert.CreateStoppageAlert(test, row).put()
    self.assertIsNotNone(
        stoppage_alert.GetStoppageAlert(test.test_path, row.revision))


if __name__ == '__main__':
  unittest.main()
