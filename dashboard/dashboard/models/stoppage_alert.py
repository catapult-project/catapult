# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The datastore model for alerts when data is no longer received for a test."""

import logging

from google.appengine.ext import ndb

from dashboard import utils
from dashboard.models import alert
from dashboard.models import alert_group

_MAX_GROUP_SIZE = 20


class StoppageAlert(alert.Alert):
  """A stoppage alert is an alert for a Test no longer receiving new points.

  Each StoppageAlert is associated with one Test, so if a test suite gets
  deprecated or renamed, there may be a set of related StoppageAlerts created.

  The key for a StoppageAlert is of the form:
    [("StoppageAlertParent", <test_path>), ("StoppageAlert", <revision>)].

  Thus, two StoppageAlert entities can not be created for the same stoppage
  event.
  """
  # Whether a mail notification has been sent for this alert.
  mail_sent = ndb.BooleanProperty(indexed=True, default=False)

  # Whether new points have been received for the test after this alert.
  recovered = ndb.BooleanProperty(indexed=True, default=False)

  # Computed properties are treated like member variables, so they have
  # lowercase names, even though they look like methods to pylint.
  # pylint: disable=invalid-name

  @ndb.ComputedProperty
  def revision(self):
    return self.key.id()

  @ndb.ComputedProperty
  def test(self):
    return utils.TestKey(self.key.parent().string_id())

  @ndb.ComputedProperty
  def row(self):
    test_container = utils.GetTestContainerKey(self.test)
    return ndb.Key('Row', self.revision, parent=test_container)

  @ndb.ComputedProperty
  def start_revision(self):
    return self.revision

  @ndb.ComputedProperty
  def end_revision(self):
    return self.revision

  @ndb.ComputedProperty
  def last_row_date(self):
    row = self.row.get()
    if not row:
      logging.warning('No Row with key %s', self.row)
      return None
    return row.timestamp


def GetStoppageAlert(test_path, revision):
  """Gets a StoppageAlert entity if it already exists.

  Args:
    test_path: The test path string of the Test associated with the alert.
    revision: The ID of the last point before the stoppage.

  Returns:
    A StoppageAlert entity or None.
  """
  return ndb.Key(
      'StoppageAlertParent', test_path, 'StoppageAlert', revision).get()


def CreateStoppageAlert(test, row):
  """Creates a new StoppageAlert entity.

  Args:
    test: A Test entity.
    row: A Row entity; the last Row that was put before the stoppage.

  Returns:
    A new StoppageAlert entity which has not been put, or None,
    if we don't want to create a new StoppageAlert.
  """
  new_alert = StoppageAlert(
      parent=ndb.Key('StoppageAlertParent', test.test_path),
      id=row.revision,
      internal_only=test.internal_only,
      sheriff=test.sheriff)
  alert_group.GroupAlerts([new_alert], test.suite_name, 'StoppageAlert')
  grouped_alert_keys = StoppageAlert.query(
      StoppageAlert.group == new_alert.group).fetch(keys_only=True)
  if len(grouped_alert_keys) >= _MAX_GROUP_SIZE:
    # Too many stoppage alerts in this group; we don't want to put any more.
    return None
  test.stoppage_alert = new_alert.key
  test.put()
  return new_alert
