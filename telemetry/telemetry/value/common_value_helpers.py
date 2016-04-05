# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.value import failure
from telemetry.value import improvement_direction
from telemetry.value import scalar


def TranslateMreFailure(mre_failure, page):
  return failure.FailureValue.FromMessage(page, mre_failure.stack)


def TranslateScalarValue(scalar_value, page):
  assert IsScalarNumericValue(scalar_value)

  value = scalar_value['numeric']['value']
  scalar_value['value'] = value
  if value is None:
    scalar_value['none_value_reason'] = 'Common scalar contained None'

  name = scalar_value['grouping_keys']['name']

  unit_parts = scalar_value['numeric']['unit'].split('_')
  if len(unit_parts) != 2:
    raise ValueError('Must specify improvement direction for value ' + name)

  scalar_value['units'] = unit_parts[0]
  scalar_value['description'] = scalar_value.get('options', {}).get(
      'description')

  if unit_parts[1] == 'biggerIsBetter':
    scalar_value['improvement_direction'] = improvement_direction.UP
  else:
    assert unit_parts[1] == 'smallerIsBetter'
    scalar_value['improvement_direction'] = improvement_direction.DOWN

  scalar_value['page_id'] = page.id
  scalar_value['name'] = name
  del scalar_value['grouping_keys']['name']
  return scalar.ScalarValue.FromDict(scalar_value, {page.id: page})


def IsScalarNumericValue(value_dict):
  return (value_dict.get('type') == 'numeric' and
          value_dict['numeric'].get('type') == 'scalar')
