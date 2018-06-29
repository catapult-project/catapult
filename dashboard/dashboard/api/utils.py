# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def ParseBool(value):
  """Parse a string representation into a True/False value."""
  if value is None:
    return None
  value_lower = value.lower()
  if value_lower in ('true', '1'):
    return True
  elif value_lower in ('false', '0'):
    return False
  else:
    raise ValueError(value)
