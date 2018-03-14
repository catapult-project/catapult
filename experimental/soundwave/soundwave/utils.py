# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import datetime


def IsoFormatStrToTimestamp(value):
  # Parse a string produced by datetime.isoformat(), assuming UTC time zone,
  # and convert to a Unix timestamp.
  try:
    d = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
  except ValueError:
    d = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
  return calendar.timegm(d.timetuple())
