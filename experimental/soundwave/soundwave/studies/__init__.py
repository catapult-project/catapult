#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pandas  # pylint: disable=import-error

from soundwave.studies import health_study
from soundwave.studies import v8_study


_STUDIES = {'health': health_study, 'v8': v8_study}

NAMES = sorted(_STUDIES)


def IterTestPaths(api, study):
  return _STUDIES[study].IterTestPaths(api)


def PostProcess(df):
  # Snap stories on the same test run to the same timestamp.
  df['timestamp'] = df.groupby(
      ['test_suite', 'bot', 'point_id'])['timestamp'].transform('min')

  # We use all runs on the latest day for each quarter as reference.
  df['quarter'] = df['timestamp'].dt.to_period('Q')
  df['reference'] = df['timestamp'].dt.date == df.groupby(
      'quarter')['timestamp'].transform('max').dt.date

  # Change unit for values in ms to seconds.
  # TODO: Get and use unit information from the dashboard instead of trying to
  # guess by the measurement name.
  is_ms_unit = (df['measurement'].str.startswith('timeTo') |
                df['measurement'].str.endswith(':duration'))
  df.loc[is_ms_unit, 'value'] = df['value'] / 1000

  return df
