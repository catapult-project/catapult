# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The database model for an "Anomaly", which represents a step up or down."""

import sys

from google.appengine.ext import ndb

from dashboard.models import alert

# A string to describe the magnitude of a change from zero to non-zero.
FREAKIN_HUGE = 'zero-to-nonzero'

# Possible improvement directions for a change. An Anomaly will always have a
# direction of UP or DOWN, but a test's improvement direction can be UNKNOWN.
UP, DOWN, UNKNOWN = (0, 1, 4)


class Anomaly(alert.Alert):
  """Represents a change-point or step found in the data series for a test.

  An Anomaly can be an upward or downward change, and can represent an
  improvement or a regression.
  """
  # The number of points before and after this anomaly that were looked at
  # when finding this anomaly.
  segment_size_before = ndb.IntegerProperty(indexed=False)
  segment_size_after = ndb.IntegerProperty(indexed=False)

  # The medians of the segments before and after the anomaly.
  median_before_anomaly = ndb.FloatProperty(indexed=False)
  median_after_anomaly = ndb.FloatProperty(indexed=False)

  # The standard deviation of the segments before the anomaly.
  std_dev_before_anomaly = ndb.FloatProperty(indexed=False)

  # The number of points that were used in the before/after segments.
  # This is also  returned by FindAnomalies
  window_end_revision = ndb.IntegerProperty(indexed=False)

  # In order to estimate how likely it is that this anomaly is due to noise,
  # t-test may be performed on the points before and after. The t-statistic,
  # degrees of freedom, and p-value are potentially-useful intermediary results.
  t_statistic = ndb.FloatProperty(indexed=False)
  degrees_of_freedom = ndb.FloatProperty(indexed=False)
  p_value = ndb.FloatProperty(indexed=False)

  # Whether this anomaly represents an improvement; if false, this anomaly is
  # considered to be a regression.
  is_improvement = ndb.BooleanProperty(indexed=True, default=False)

  # Whether this anomaly recovered (i.e. if this is a step down, whether there
  # is a corresponding step up later on, or vice versa.)
  recovered = ndb.BooleanProperty(indexed=True, default=False)

  @property
  def percent_changed(self):
    """The percent change from before the anomaly to after."""
    if self.median_before_anomaly == 0.0:
      return sys.float_info.max
    difference = self.median_after_anomaly - self.median_before_anomaly
    return 100 * difference / self.median_before_anomaly

  @property
  def direction(self):
    """Whether the change is numerically an increase or decrease."""
    if self.median_before_anomaly < self.median_after_anomaly:
      return UP
    return DOWN

  def GetDisplayPercentChanged(self):
    """Gets a string showing the percent change."""
    if abs(self.percent_changed) == sys.float_info.max:
      return FREAKIN_HUGE
    else:
      return str('%.1f%%' % abs(self.percent_changed))

  def SetIsImprovement(self, test=None):
    """Sets whether the alert is an improvement for the given test."""
    if not test:
      test = self.GetTestMetadataKey().get()
    # |self.direction| is never equal to |UNKNOWN| (see the definition above)
    # so when the test improvement direction is |UNKNOWN|, |self.is_improvement|
    # will be False.
    self.is_improvement = (self.direction == test.improvement_direction)
