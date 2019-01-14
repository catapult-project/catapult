# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import gtest_json_converter
from tracing.value.diagnostics import reserved_infos


NANO_TO_MILLISECONDS = 0.000001


class GtestJsonConverterUnittest(unittest.TestCase):

  def testConvertBasic(self):
    data = {
        'metric1': {
            'units': 'ms',
            'traces': {
                'story1': ['10.12345', '0.54321'],
                'story2': ['30', '0'],
            }
        },
        'metric2': {
            'units': 'ns',
            'traces': {
                'story1': ['100000.0', '2543.543'],
                'story2': ['12345.6789', '301.2'],
            },
        }
    }
    histograms = gtest_json_converter.ConvertGtestJson(data)
    self.assertEqual(len(histograms), 4)

    metric_histograms = histograms.GetHistogramsNamed('metric1')
    self.assertEqual(len(metric_histograms), 2)
    story1 = None
    story2 = None
    if metric_histograms[0].diagnostics[
        reserved_infos.STORIES.name].GetOnlyElement() == 'story1':
      story1 = metric_histograms[0]
      story2 = metric_histograms[1]
    else:
      story2 = metric_histograms[0]
      story1 = metric_histograms[1]

    # assertAlmostEqual necessary to avoid floating point precision issues.
    self.assertAlmostEqual(story1.average, 10.12345)
    self.assertAlmostEqual(story1.standard_deviation, 0.54321)
    self.assertEqual(story2.average, 30)
    self.assertEqual(story2.standard_deviation, 0)
    self.assertEqual(story1.unit, story2.unit)
    self.assertEqual(story1.unit, 'ms_smallerIsBetter')

    metric_histograms = histograms.GetHistogramsNamed('metric2')
    self.assertEqual(len(metric_histograms), 2)
    if metric_histograms[0].diagnostics[
        reserved_infos.STORIES.name].GetOnlyElement() == 'story1':
      story1 = metric_histograms[0]
      story2 = metric_histograms[1]
    else:
      story2 = metric_histograms[0]
      story1 = metric_histograms[1]

    # assertAlmostEqual necessary to avoid floating point precision issues.
    # We expect the numbers to be different than what was initially provided
    # since this should be converted to milliseconds.
    self.assertAlmostEqual(story1.average, 100000 * NANO_TO_MILLISECONDS)
    self.assertAlmostEqual(story1.standard_deviation,
                           2543.543 * NANO_TO_MILLISECONDS)
    self.assertAlmostEqual(story2.average, 12345.6789 * NANO_TO_MILLISECONDS)
    self.assertAlmostEqual(story2.standard_deviation,
                           301.2 * NANO_TO_MILLISECONDS)
    self.assertEqual(story1.unit, story2.unit)
    self.assertEqual(story1.unit, 'msBestFitFormat_smallerIsBetter')

  def testConvertUnknownUnit(self):
    data = {
        'metric1': {
            'units': 'SomeUnknownUnit',
            'traces': {
                'story1': ['10', '1'],
                'story2': ['123.4', '7.89'],
            }
        }
    }
    histograms = gtest_json_converter.ConvertGtestJson(data)
    self.assertEqual(len(histograms), 2)

    metric_histograms = histograms.GetHistogramsNamed('metric1')
    self.assertEqual(len(metric_histograms), 2)
    story1 = None
    story2 = None
    if metric_histograms[0].diagnostics[
        reserved_infos.STORIES.name].GetOnlyElement() == 'story1':
      story1 = metric_histograms[0]
      story2 = metric_histograms[1]
    else:
      story2 = metric_histograms[0]
      story1 = metric_histograms[1]

    self.assertEqual(story1.average, 10)
    self.assertEqual(story1.standard_deviation, 1)
    self.assertAlmostEqual(story2.average, 123.4)
    self.assertAlmostEqual(story2.standard_deviation, 7.89)
    self.assertEqual(story1.unit, story2.unit)
    self.assertEqual(story1.unit, 'unitless_smallerIsBetter')
