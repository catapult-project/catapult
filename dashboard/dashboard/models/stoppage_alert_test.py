# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


class StoppageAlertTest(testing_common.TestCase):

  def _AddSampleData(self):
    """Puts a TestMetadata and Row in the datastore and returns the entities."""
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

  def testCreateStoppageAlert_DoesNotCreateLargeGroups(self):
    # First, create |_MAX_GROUP_SIZE| alerts; all of them can be created
    # and they all belong to the same group.
    tests = map(str, range(stoppage_alert._MAX_GROUP_SIZE))
    testing_common.AddTests(['M'], ['b'], {'suite': {t: {} for t in tests}})
    test_paths = ['M/b/suite/' + t for t in tests]
    rows = []
    alerts = []
    for path in test_paths:
      rows = testing_common.AddRows(path, [1])
      test = utils.TestKey(path).get()
      new_alert = stoppage_alert.CreateStoppageAlert(test, rows[0])
      self.assertIsNotNone(new_alert)
      new_alert.put()
      alerts.append(new_alert)
    self.assertEqual(stoppage_alert._MAX_GROUP_SIZE, len(alerts))
    self.assertTrue(all(a.group == alerts[0].group for a in alerts))

    # Making one more stoppage alert that belongs to this group fails.
    testing_common.AddTests(['M'], ['b'], {'suite': {'another': {}}})
    test_path = 'M/b/suite/another'
    rows = testing_common.AddRows(test_path, [1])
    test = utils.TestKey(test_path).get()
    new_alert = stoppage_alert.CreateStoppageAlert(test, rows[0])
    self.assertIsNone(new_alert)


if __name__ == '__main__':
  unittest.main()
