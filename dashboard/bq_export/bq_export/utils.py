# Copyright (c) 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import math


## Copy of dashboard.common.utils.TestPath for google.cloud.datastore.key.Key
## rather than ndb.Key.
def TestPath(key):
  if key.kind == 'Test':
    # The Test key looks like ('Master', 'name', 'Bot', 'name', 'Test' 'name'..)
    # Pull out every other entry and join with '/' to form the path.
    return '/'.join(key.flat_path[1::2])
  assert key.kind == 'TestMetadata' or key.kind == 'TestContainer'
  return key.name


def DaysAgoTimestamp(days_ago):
  """Return a datetime for a day the given number of days in the past."""
  now = datetime.datetime.now()
  result_datetime = now - datetime.timedelta(days=days_ago)
  return result_datetime


def FloatHack(f):
  """Workaround BQ streaming inserts not supporting inf and NaN values.

  Somewhere between Beam and the BigQuery streaming inserts API infinities and
  NaNs break if passed as is, apparently because JSON cannot represent these
  values natively.  Fortunately BigQuery appears happy to cast string values
  into floats, so we just have to intercept these values and substitute strings.

  Nones, and floats other than inf and NaN, are returned unchanged.
  """
  if f is None:
    return None
  if math.isinf(f):
    return 'inf' if f > 0 else '-inf'
  if math.isnan(f):
    return 'NaN'
  return f
