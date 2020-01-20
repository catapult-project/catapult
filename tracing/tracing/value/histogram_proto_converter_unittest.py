# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
import unittest

from tracing.value import histogram_proto_converter
from tracing.value import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import generic_set


def _Hist(unit=None,
          bin_boundaries=None,
          diagnostics=None,
          running=None,
          all_bins=None,
          summary_options=None):
  unit = unit or {'unit': 'MS'}
  result = {
      'name': 'whatever!',
      'unit': unit,
      'description': 'don\'t care!',
  }
  if bin_boundaries:
    result['binBoundaries'] = bin_boundaries
  if diagnostics:
    result['diagnostics'] = diagnostics
  if running:
    result['running'] = running
  if all_bins:
    result['allBins'] = all_bins
  if summary_options:
    result['summaryOptions'] = summary_options

  return result


class HistogramProtoConverterUnittest(unittest.TestCase):

  def testUnitsAreInSync(self):
    # The /5 is because unit map is populated with five variants: plain,
    # biggerIsBetter, smallerIsBetter, +, -.
    expected_num_base_units = len(histogram.UNIT_NAMES) / 5

    self.assertEqual(
        len(histogram_proto_converter.UNIT_MAP),
        expected_num_base_units,
        msg='Keep UNIT_MAP and UNIT_NAMES in sync please.')

  def testMinimalValidHistogram(self):
    hist_dict = histogram_proto_converter.ConvertHistogram({
        'name': 'name!',
        'unit': {
            'unit': 'UNITLESS'
        },
    })

    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.name, 'name!')
    self.assertEqual(hist.unit, 'unitless')

  def testSimpleFields(self):
    hist_dict = histogram_proto_converter.ConvertHistogram({
        'name': 'whatever',
        'unit': {
            'unit': 'MS'
        },
        'description': 'description!',
        'sampleValues': [21, 22, 23],
        'maxNumSampleValues': 3,
        'numNans': 1,
    })

    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.description, 'description!')
    self.assertEqual(hist.sample_values, [21, 22, 23])
    self.assertEqual(hist.max_num_sample_values, 3)
    self.assertEqual(hist.num_nans, 1)

  def testRaisesCustomExceptionOnMissingMandatoryFields(self):
    with self.assertRaises(ValueError):
      # Missing name.
      histogram_proto_converter.ConvertHistogram({})
    with self.assertRaises(ValueError):
      # Missing unit.
      histogram_proto_converter.ConvertHistogram({'name': 'eh'})

  def testUnitWithImprovementSmallerIsBetter(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(unit={
            'unit': 'TS_MS',
            'improvement_direction': 'SMALLER_IS_BETTER'
        }))
    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.unit, 'tsMs_smallerIsBetter')

  def testUnitWithImprovementBiggerIsBetter(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(unit={
            'unit': 'SIGMA',
            'improvement_direction': 'BIGGER_IS_BETTER'
        }))
    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.unit, 'sigma_biggerIsBetter')

  def testUnitWithImprovementDontCare(self):
    # Don't care should not really be set - protobuf doesn't write it out in the
    # JSON because it's the base enum.
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(unit={
            'unit': 'HERTZ',
            'improvement_direction': 'NOT_SPECIFIED'
        }))
    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.unit, 'Hz')

  def testMinimalBinBounds(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(bin_boundaries={
            'firstBinBoundary': 1,
        }))

    bins = hist_dict['binBoundaries']
    self.assertEqual(bins, [1])

  def testComplexBinBounds(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(
            bin_boundaries={
                'firstBinBoundary':
                    17,
                'binSpecs': [{
                    'binBoundary': 18
                }, {
                    'binSpec': {
                        'boundaryType': 'EXPONENTIAL',
                        'maximumBinBoundary': 19,
                        'numBinBoundaries': 20
                    },
                }, {
                    'binSpec': {
                        'boundaryType': 'LINEAR',
                        'maximumBinBoundary': 21,
                        'numBinBoundaries': 22
                    }
                }]
            }))

    # Don't parse this into a histogram for this case. The format for bins is
    # relatively easily understood, whereas how bins are generated is very
    # complex. See the histogram spec in docs/histogram-set-json-format.md.
    bins = hist_dict['binBoundaries']
    self.assertEqual(bins, [17, 18, [1, 19, 20], [0, 21, 22]])

  def testBasicDiagnostics(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(
            diagnostics={
                'diagnosticMap': {
                    'myDiagnostic': {
                        'genericSet': {
                            'values': ["\"some value\""]
                        }
                    },
                }
            }))

    hist = histogram.Histogram.FromDict(hist_dict)

    expected = generic_set.GenericSet(values=['some value'])
    self.assertEqual(hist.diagnostics['myDiagnostic'], expected)

  def testUnsupportedDiagnostics(self):
    with self.assertRaises(ValueError):
      histogram_proto_converter.ConvertHistogram(
          _Hist(diagnostics={
              'diagnosticMap': {
                  'myDiagnostic': {
                      'breakdown': {}
                  },
              }
          }))

  def testGenericSetWithInvalidJson(self):
    with self.assertRaises(TypeError):
      histogram_proto_converter.ConvertHistogram(
          _Hist(
              diagnostics={
                  'diagnosticMap': {
                      'myDiagnostic': {
                          'genericSet': {
                              'values':
                                  ['this_is_an_undefined_json_indentifier']
                          }
                      },
                  }
              }))

  def testSharedDiagnosticsAreMappedIntoHistogram(self):
    guid1 = 'f7f17394-fa4a-481e-86bd-a82cd55935a7'
    guid2 = '88ea36c7-6dcb-4ba8-ba56-1979de05e16f'

    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(
            diagnostics={
                'diagnosticMap': {
                    'bots': {
                        'sharedDiagnosticGuid': guid1,
                    },
                    'pointId': {
                        'sharedDiagnosticGuid': guid2,
                    },
                }
            }))

    shared_diagnostics = histogram_proto_converter.ConvertSharedDiagnostics({
        guid1: {
            'genericSet': {
                'values': ['"webrtc_perf_tests"',]
            },
        },
        guid2: {
            'genericSet': {
                'values': ['123456',]
            },
        },
        'some other guid': {
            'genericSet': {
                'values': ['2']
            }
        }
    })

    # Import into a HistogramSet since it does the resolving of shared
    # diagnostics.
    hist_set = histogram_set.HistogramSet()
    for shared in shared_diagnostics:
      hist_set.ImportLegacyDict(shared)
    hist_set.ImportLegacyDict(hist_dict)
    hist = hist_set.GetFirstHistogram()

    self.assertIsNotNone(hist)
    self.assertEqual(len(hist.diagnostics), 2)

    self.assertEqual(hist.diagnostics['pointId'],
                     generic_set.GenericSet(values=[123456]))
    self.assertEqual(hist.diagnostics['bots'],
                     generic_set.GenericSet(values=['webrtc_perf_tests']))

  def testRunningStatistics(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(
            running={
                'count': 4,
                'max': 23,
                'meanlogs': 1,
                'mean': 22,
                'min': 21,
                'sum': 66,
                'variance': 1
            }))

    hist = histogram.Histogram.FromDict(hist_dict)

    # We get at meanlogs through geometric_mean. Variance is after Bessel's
    # correction has been applied.
    self.assertEqual(hist.running.count, 4)
    self.assertEqual(hist.running.max, 23)
    self.assertEqual(hist.running.geometric_mean, math.exp(1))
    self.assertEqual(hist.running.mean, 22)
    self.assertEqual(hist.running.min, 21)
    self.assertEqual(hist.running.sum, 66)
    self.assertAlmostEqual(hist.running.variance, 0.3333333333)

  def testMinimalStats(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(running={
            # The proto will not write ints that are 0 on the wire.
            'count': 1
        }))

    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(hist.running.count, 1)
    self.assertEqual(hist.running.mean, 0)
    self.assertEqual(hist.running.variance, 0)

  def testAllBins(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(
            all_bins={
                '0': {
                    'binCount':
                        24,
                    'diagnosticMaps': [{
                        'diagnosticMap': {
                            'some bin diagnostic': {
                                'genericSet': {
                                    'values': ["\"some value\""]
                                }
                            }
                        }
                    }, {
                        'diagnosticMap': {
                            'other bin diagnostic': {
                                'genericSet': {
                                    'values': ["\"some other value\""]
                                }
                            }
                        }
                    }]
                }
            }))

    hist = histogram.Histogram.FromDict(hist_dict)

    self.assertEqual(len(hist.bins), 1)
    self.assertEqual(len(hist.bins[0].diagnostic_maps), 2)
    self.assertEqual(len(hist.bins[0].diagnostic_maps[0]), 1)
    self.assertEqual(len(hist.bins[0].diagnostic_maps[1]), 1)
    self.assertEqual(hist.bins[0].diagnostic_maps[0]['some bin diagnostic'],
                     generic_set.GenericSet(values=['some value']))
    self.assertEqual(hist.bins[0].diagnostic_maps[1]['other bin diagnostic'],
                     generic_set.GenericSet(values=['some other value']))

  def testSummaryOptions(self):
    hist_dict = histogram_proto_converter.ConvertHistogram(
        _Hist(summary_options={
            'nans': False,
            'geometricMean': False,
            'percentile': [0.90, 0.95, 0.99]
        }))

    hist = histogram.Histogram.FromDict(hist_dict)

    # See the histogram spec in docs/histogram-set-json-format.md.
    self.assertEqual(
        hist.statistics_names,
        set([
            'std', 'count', 'pct_090', 'pct_095', 'max', 'sum', 'min',
            'pct_099', 'avg'
        ]))
