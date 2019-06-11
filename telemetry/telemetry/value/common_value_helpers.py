# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.value import improvement_direction
from telemetry.value import scalar


_DIRECTION = {
    'biggerIsBetter': improvement_direction.UP,
    'smallerIsBetter': improvement_direction.DOWN
}


def TranslateScalarValue(scalar_value, page):
  # Parses scalarDicts created by:
  #   tracing/tracing/metrics/metric_map_function.html
  # back into ScalarValue's.
  value = scalar_value['numeric']['value']
  none_value_reason = None
  if value is None:
    none_value_reason = 'Common scalar contained None'
  elif value in ['Infinity', '-Infinity', 'NaN']:
    none_value_reason = 'value was %s' % value
    value = None
  name = scalar_value['name']
  unit_parts = scalar_value['numeric']['unit'].split('_')
  if len(unit_parts) != 2:
    raise ValueError('Must specify improvement direction for value ' + name)
  return scalar.ScalarValue(page, name, unit_parts[0], value,
                            description=scalar_value['description'],
                            none_value_reason=none_value_reason,
                            improvement_direction=_DIRECTION[unit_parts[1]])
