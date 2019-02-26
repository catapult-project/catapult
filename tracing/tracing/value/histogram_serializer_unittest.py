# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram
from tracing.value import histogram_serializer
from tracing.value.diagnostics import breakdown
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import related_event_set
from tracing.value.diagnostics import related_name_map


class HistogramSerializerUnittest(unittest.TestCase):
  def testObjects(self):
    serializer = histogram_serializer.HistogramSerializer()
    self.assertEqual(0, serializer.GetOrAllocateId('a'))
    self.assertEqual(1, serializer.GetOrAllocateId(['b']))
    self.assertEqual(0, serializer.GetOrAllocateId('a'))
    self.assertEqual(1, serializer.GetOrAllocateId(['b']))

  def testDiagnostics(self):
    serializer = histogram_serializer.HistogramSerializer()
    self.assertEqual(0, serializer.GetOrAllocateDiagnosticId(
        'a', generic_set.GenericSet(['b'])))
    self.assertEqual(1, serializer.GetOrAllocateDiagnosticId(
        'a', generic_set.GenericSet(['c'])))
    self.assertEqual(0, serializer.GetOrAllocateDiagnosticId(
        'a', generic_set.GenericSet(['b'])))
    self.assertEqual(1, serializer.GetOrAllocateDiagnosticId(
        'a', generic_set.GenericSet(['c'])))

  def testSerialize(self):
    hist = histogram.Histogram('aaa', 'count_biggerIsBetter')
    hist.description = 'lorem ipsum'
    hist.diagnostics['bbb'] = related_name_map.RelatedNameMap({
        'ccc': 'a:c',
        'ddd': 'a:d',
    })
    hist.diagnostics['hhh'] = generic_set.GenericSet(['ggg'])
    hist.AddSample(0, {
        'bbb': breakdown.Breakdown.FromEntries({
            'ccc': 11,
            'ddd': 31,
        }),
        'eee': related_event_set.RelatedEventSet([{
            'stableId': 'fff',
            'title': 'ggg',
            'start': 3,
            'duration': 4,
        }]),
    })

    data = histogram_serializer.Serialize([hist])
    self.assertEqual(data, [
        [
            'aaa',
            [1, [1, 1000.0, 20]],
            '',
            'ccc',
            'ddd',
            [3, 4],
            'ggg',
            'avg', 'count', 'max', 'min', 'std', 'sum',
            'lorem ipsum',
            'a:c',
            'a:d',
        ],
        {
            'Breakdown': {'bbb': {5: [2, 5, 11, 31]}},
            'GenericSet': {
                'hhh': {0: 6},
                'statisticsNames': {1: [7, 8, 9, 10, 11, 12]},
                'description': {3: 13},
            },
            'RelatedEventSet': {'eee': {4: [['fff', 6, 3, 4]]}},
            'RelatedNameMap': {'bbb': {2: [5, 14, 15]}},
        },
        [
            0,
            'count+',
            1,
            [0, 1, 2, 3],
            [1, 0, None, 0, 0, 0, 0],
            {0: [1, [None, 4, 5]]},
            0,
        ]
    ])
