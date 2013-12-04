# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Backward compatibility for old results API.

This module helps convert the old PageMeasurementResults API into the new
style one. This exists as a bridging solution so we can change the underlying
implementation and update the PageMeasurementResults API once we know the
underlying implementation is solid.
"""
from telemetry import value as value_module
from telemetry.value import histogram
from telemetry.value import list_of_scalar_values
from telemetry.value import scalar


def ConvertOldCallingConventionToValue(page, trace_name, units,
                                       value, chart_name, data_type):
  value_name = value_module.ValueNameFromTraceAndChartName(
      trace_name, chart_name)
  if data_type == 'default':
    if isinstance(value, list):
      return list_of_scalar_values.ListOfScalarValues(
          page, value_name, units, value, important=True)
    else:
      return scalar.ScalarValue(page, value_name, units,
                                value, important=True)
  elif data_type == 'unimportant':
    if isinstance(value, list):
      return list_of_scalar_values.ListOfScalarValues(
          page, value_name, units, value, important=False)
    else:
      return scalar.ScalarValue(page, value_name, units,
                                value, important=False)
  elif data_type == 'histogram':
    assert isinstance(value, basestring)
    return histogram.HistogramValue(
        page, value_name, units, raw_value_json=value, important=True)
  elif data_type == 'unimportant-histogram':
    assert isinstance(value, basestring)
    return histogram.HistogramValue(
        page, value_name, units, raw_value_json=value, important=False)
  elif data_type == 'informational':
    raise NotImplementedError()
  else:
    raise ValueError('Unrecognized data type %s', data_type)
