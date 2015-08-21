# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb

from dashboard import testing_common
from dashboard import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


class AnomalyGroupingTest(testing_common.TestCase):
  """Test case for the behavior of updating anomaly groups."""

  def _AddAnomalies(self):
    """Adds a set of sample data used in the tests below."""
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'],
        {'scrolling_benchmark': {'first_paint': {}}})
    first_paint_key = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/first_paint')
    first_paint_test = first_paint_key.get()
    first_paint_test.improvement_direction = anomaly.DOWN
    first_paint_test.put()

    group_keys = [
        alert_group.AlertGroup(
            start_revision=3000,
            end_revision=4000,
            alert_kind='Anomaly',
            test_suites=['scrolling_benchmark']).put(),
        alert_group.AlertGroup(
            start_revision=6000,
            end_revision=8000,
            alert_kind='Anomaly',
            test_suites=['scrolling_benchmark']).put(),
    ]

    anomaly_keys = [
        anomaly.Anomaly(
            start_revision=2000,
            end_revision=4000,
            bug_id=12345,
            test=first_paint_key).put(),
        anomaly.Anomaly(
            start_revision=3000,
            end_revision=5000,
            bug_id=12345,
            test=first_paint_key).put(),
        anomaly.Anomaly(
            start_revision=6000,
            end_revision=8000,
            bug_id=None,
            test=first_paint_key).put(),
    ]

    anomalies = ndb.get_multi(anomaly_keys)

    # Add these anomalies to groups and put them again. When anomalies are
    # put for the second time onward, the pre-put hook will be called and
    # the groups of the anomalies will be updated.
    anomalies[0].group = group_keys[0]
    anomalies[0].put()
    anomalies[1].group = group_keys[0]
    anomalies[1].put()
    anomalies[2].group = group_keys[1]
    anomalies[2].put()

    # Note that after these anomalies are added, the state of the two groups
    # is updated. Also, the first two anomalies are in the same group.
    self.assertEqual(anomalies[0].group, anomalies[1].group)
    self.assertNotEqual(anomalies[0].group, anomalies[2].group)
    return anomalies

  def testUpdateAnomalyBugId_UpdatesGroupOfAnomaly(self):
    anomalies = self._AddAnomalies()

    # At first, two anomalies are in separate groups, and the second anomaly
    # has not been assigned a bug ID.
    self.assertNotEqual(anomalies[1].group, anomalies[2].group)
    self.assertEqual(12345, anomalies[1].bug_id)
    self.assertIsNone(anomalies[2].bug_id)

    # Test setting bug_id. Anomaly should be moved to new group.
    anomalies[2].bug_id = 12345
    anomalies[2].put()
    self.assertEqual(anomalies[1].bug_id, anomalies[2].bug_id)

  def testMarkAnomalyInvalid_AnomalyIsRemovedFromGroup(self):
    anomalies = self._AddAnomalies()

    # At first, two anomalies are in the same group.
    self.assertEqual(anomalies[0].group, anomalies[1].group)

    # Mark one of the alerts as invalid.
    self.assertEqual(12345, anomalies[1].bug_id)
    anomalies[1].bug_id = -1
    anomalies[1].put()

    # Now, the alert marked as invalid has no group.
    # Also, the group's revision range has been updated accordingly.
    self.assertNotEqual(anomalies[0].group, anomalies[1].group)
    self.assertIsNone(anomalies[1].group)
    group = anomalies[0].group.get()
    self.assertEqual(2000, group.start_revision)
    self.assertEqual(4000, group.end_revision)

  def testUpdateAnomalyRevisionRange_UpdatesGroupRevisionRange(self):
    anomalies = self._AddAnomalies()

    # Add another anomaly to the same group as the first two anomalies,
    # but with a non-overlapping revision range.
    new_anomaly = anomaly.Anomaly(
        start_revision=3000,
        end_revision=4000,
        group=anomalies[0].group)
    new_anomaly.put()

    # Associate it with a group; the pre-put hook will update the group's
    # revision range here.
    new_anomaly.start_revision = 3010
    new_anomaly.end_revision = 3020
    new_anomaly.put()

    # Now the group's revision range is updated.
    group = anomalies[0].group.get()
    self.assertEqual(3010, group.start_revision)
    self.assertEqual(3020, group.end_revision)

  def testUpdateGroup_InvalidRange_PropertiesAreUpdated(self):
    anomalies = self._AddAnomalies()

    # Add another anomaly to the same group as the first two anomalies
    # by setting its bug ID to match that of an existing group.
    new_anomaly = anomaly.Anomaly(
        start_revision=3000,
        end_revision=4000,
        group=anomalies[0].group)
    new_anomaly_key = new_anomaly.put()

    # Change the anomaly revision to invalid range.
    new_anomaly.start_revision = 10
    new_anomaly.end_revision = 20
    new_anomaly.put()

    # After adding this new anomaly, it belongs to the group, and the group
    # no longer has a minimum revision range.
    group = anomalies[0].group.get()
    self.assertEqual(anomalies[0].group, new_anomaly_key.get().group)
    self.assertIsNone(group.start_revision)
    self.assertIsNone(group.end_revision)

    # Remove the new anomaly from the group by marking it invalid.
    new_anomaly = new_anomaly_key.get()
    new_anomaly.bug_id = -1
    new_anomaly.put()

    # Now, the anomaly group's revision range is valid again.
    group = anomalies[0].group.get()
    self.assertEqual(3000, group.start_revision)
    self.assertEqual(4000, group.end_revision)


class StoppageAlertGroupingTest(testing_common.TestCase):
  """Test case for the behavior of updating StoppageAlert groups."""

  def _AddStoppageAlerts(self):
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'],
        {
            'scrolling_benchmark': {
                'dropped_foo': {},
                'dropped_bar': {},
            }
        })
    foo_path = 'ChromiumGPU/linux-release/scrolling_benchmark/dropped_foo'
    bar_path = 'ChromiumGPU/linux-release/scrolling_benchmark/dropped_bar'
    foo_test = utils.TestKey(foo_path).get()
    bar_test = utils.TestKey(bar_path).get()
    foo_row = testing_common.AddRows(foo_path, {200})[0]
    bar_row = testing_common.AddRows(bar_path, {200})[0]
    foo_alert_key = stoppage_alert.CreateStoppageAlert(foo_test, foo_row).put()
    bar_alert_key = stoppage_alert.CreateStoppageAlert(bar_test, bar_row).put()
    return [foo_alert_key.get(), bar_alert_key.get()]

  def testStoppageAlertGroup_GroupAssignedUponCreation(self):
    foo_test, bar_test = self._AddStoppageAlerts()
    self.assertIsNotNone(foo_test.group)
    self.assertIsNotNone(bar_test.group)
    self.assertEqual('StoppageAlert', foo_test.group.get().alert_kind)


class GroupAlertsTest(testing_common.TestCase):

  def _CreateAnomalyForTests(
      self, revision_range, test, sheriff_key, bug_id, is_improvement):
    """Returns a sample anomaly with some default properties."""
    anomaly_entity = anomaly.Anomaly(
        start_revision=revision_range[0], end_revision=revision_range[1],
        test=test, median_before_anomaly=100, median_after_anomaly=200,
        sheriff=sheriff_key, bug_id=bug_id, is_improvement=is_improvement)
    return anomaly_entity

  def _AddSheriffs(self):
    sheriff1 = sheriff.Sheriff(
        id='Chromium Perf Sheriff', email='chrisphan@google.com').put()
    sheriff2 = sheriff.Sheriff(
        id='QA Perf Sheriff', email='chrisphan@google.com').put()
    return [sheriff1, sheriff2]

  def _AddTests(self):
    test_data = {
        'scrolling_benchmark': {
            'first_paint': {},
        },
        'tab_capture': {
            'capture': {},
        }
    }
    testing_common.AddTests(['ChromiumGPU'], ['linux-release'], test_data)
    testing_common.AddTests(['QAPerf'], ['linux-release'], test_data)
    scrolling_test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/first_paint')
    tab_capture_test = utils.TestKey(
        'ChromiumGPU/linux-release/tab_capture/capture')
    for test_key in [scrolling_test, tab_capture_test]:
      test = test_key.get()
      test.improvement_direction = anomaly.DOWN
      test.put()
    return [scrolling_test, tab_capture_test]

  def testGroupAlerts_WithNoAssociation_MakesNewGroup(self):
    sheriffs = self._AddSheriffs()
    tests = self._AddTests()

    # Add some anomaly groups.
    alert_group.AlertGroup(
        bug_id=None,
        start_revision=3000,
        end_revision=6000,
        alert_kind='Anomaly',
        test_suites=['scrolling_benchmark']).put()
    alert_group.AlertGroup(
        bug_id=104,
        start_revision=7000,
        end_revision=9000,
        alert_kind='Anomaly',
        test_suites=['tab_capture']).put()

    improvement_anomaly = self._CreateAnomalyForTests(
        revision_range=(1000, 2000), test=tests[0], sheriff_key=sheriffs[0],
        bug_id=None, is_improvement=True)
    regression_anomaly = self._CreateAnomalyForTests(
        revision_range=(1000, 2000), test=tests[0], sheriff_key=sheriffs[0],
        bug_id=None, is_improvement=False)
    test_suite = 'scrolling_benchmark'

    alert_group.GroupAlerts(
        [regression_anomaly, improvement_anomaly], test_suite, 'Anomaly')

    # The regression Anomaly was not grouped with a group that has a bug ID,
    # so the bug ID is not changed.
    self.assertIsNone(regression_anomaly.bug_id)

    # Improvement Anomaly should not be auto-triaged.
    self.assertIsNone(improvement_anomaly.group)

    alert_groups = alert_group.AlertGroup.query().fetch()
    self.assertEqual(3, len(alert_groups))
    self.assertEqual(
        (1000, 2000),
        (alert_groups[2].start_revision, alert_groups[2].end_revision))
    self.assertIsNone(alert_groups[2].bug_id)
    self.assertEqual(alert_groups[2].test_suites, [test_suite])

  def testGroupAlerts_WithExistingGroup(self):
    sheriffs = self._AddSheriffs()
    tests = self._AddTests()

    # Add some anomaly groups.
    alert_group.AlertGroup(
        bug_id=None,
        start_revision=3000,
        end_revision=6000,
        alert_kind='Anomaly',
        test_suites=['scrolling_benchmark']).put()
    tab_capture_group = alert_group.AlertGroup(
        bug_id=104,
        start_revision=7000,
        end_revision=9000,
        alert_kind='Anomaly',
        test_suites=['tab_capture']).put()

    improvement_anomaly = self._CreateAnomalyForTests(
        revision_range=(6000, 8000), test=tests[1], sheriff_key=sheriffs[0],
        bug_id=None, is_improvement=True)
    regression_anomaly = self._CreateAnomalyForTests(
        revision_range=(6000, 8000), test=tests[1], sheriff_key=sheriffs[0],
        bug_id=None, is_improvement=False)

    alert_group.GroupAlerts(
        [regression_anomaly, improvement_anomaly], 'tab_capture', 'Anomaly')

    # The regression Anomaly's bug ID is changed because it has been grouped.
    self.assertEqual(104, regression_anomaly.bug_id)
    self.assertEqual(tab_capture_group, regression_anomaly.group)

    # Improvement Anomaly should not be grouped.
    self.assertIsNone(improvement_anomaly.group)
    alert_groups = alert_group.AlertGroup.query().fetch()
    self.assertEqual(2, len(alert_groups))
    self.assertEqual(
        (7000, 8000),
        (alert_groups[1].start_revision, alert_groups[1].end_revision))

  def testGroupAlerts_WithExistingGroupThatHasDifferentKind_DoesntGroup(self):
    sheriffs = self._AddSheriffs()
    tests = self._AddTests()
    group_key = alert_group.AlertGroup(
        bug_id=None,
        start_revision=3000,
        end_revision=6000,
        alert_kind='OtherAlert',
        test_suites=['tab_capture']).put()
    my_alert = self._CreateAnomalyForTests(
        revision_range=(4000, 5000), test=tests[1], sheriff_key=sheriffs[0],
        bug_id=None, is_improvement=False)

    alert_group.GroupAlerts([my_alert], 'tab_capture', 'Anomaly')
    self.assertNotEqual(group_key, my_alert.group)
    self.assertEqual('Anomaly', my_alert.group.get().alert_kind)

    # If the alert kind that's passed when calling GroupAlerts matches
    # the alert kind of the existing group, then it will be grouped.
    alert_group.GroupAlerts([my_alert], 'tab_capture', 'OtherAlert')
    self.assertEqual(group_key, my_alert.group)
    self.assertEqual('OtherAlert', my_alert.group.get().alert_kind)


if __name__ == '__main__':
  unittest.main()
