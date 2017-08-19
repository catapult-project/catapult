# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import sys
import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import add_histograms_queue
from dashboard import add_point_queue
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value import histogram as histogram_module
from tracing.value.diagnostics import reserved_infos

TEST_HISTOGRAM = {
    'allBins': {'1': [1], '3': [1], '4': [1]},
    'binBoundaries': [1, [1, 1000, 20]],
    'diagnostics': {
        reserved_infos.CHROMIUM_COMMIT_POSITIONS.name: {
            'values': [123],
            'type': 'GenericSet'
        },
        reserved_infos.V8_REVISIONS.name: {
            'values': ['4cd34ad3320db114ad3a2bd2acc02aba004d0cb4'],
            'type': 'GenericSet'
        },
        'owners': '68e5b3bd-829c-4f4f-be3a-98a94279ccf0',
        'benchmarks': 'ec2c0cdc-cd9f-4736-82b4-6ffc3d76e3eb'
    },
    'guid': 'c2c0fa00-060f-4d56-a1b7-51fde4767584',
    'name': 'foo',
    'running': [3, 3, 0.5972531564093516, 2, 1, 6, 2],
    'sampleValues': [1, 2, 3],
    'unit': 'count_biggerIsBetter'
}


TEST_BENCHMARKS = {
    'guid': 'ec2c0cdc-cd9f-4736-82b4-6ffc3d76e3eb',
    'values': ['myBenchmark'],
    'type': 'GenericSet',
}


TEST_OWNERS = {
    'guid': '68e5b3bd-829c-4f4f-be3a-98a94279ccf0',
    'values': ['abc@chromium.org'],
    'type': 'GenericSet'
}


class AddHistogramsQueueTest(testing_common.TestCase):
  def setUp(self):
    super(AddHistogramsQueueTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms_queue',
         add_histograms_queue.AddHistogramsQueueHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPostHistogram(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])

    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_HISTOGRAM),
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)

    test = test_key.get()
    self.assertEqual(test.units, 'count_biggerIsBetter')
    self.assertEqual(test.improvement_direction, anomaly.UP)

    master = ndb.Key('Master', 'Chromium').get()
    self.assertIsNotNone(master)

    bot = ndb.Key('Master', 'Chromium', 'Bot', 'win7').get()
    self.assertIsNotNone(bot)

    tests = graph_data.TestMetadata.query().fetch()
    self.assertEqual(2, len(tests))

    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))
    self.assertEqual(TEST_HISTOGRAM['guid'], histograms[0].key.id())

    h = histograms[0]
    self.assertEqual(json.dumps(TEST_HISTOGRAM), h.data)
    self.assertEqual(test_key, h.test)
    self.assertEqual(123, h.revision)
    self.assertFalse(h.internal_only)

  def testPostHistogram_Internal(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['mac'])

    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_HISTOGRAM),
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)
    original_histogram = TEST_HISTOGRAM

    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))
    self.assertEqual(original_histogram['guid'], histograms[0].key.id())

    h = histograms[0]
    self.assertEqual(json.dumps(TEST_HISTOGRAM), h.data)
    self.assertEqual(test_key, h.test)
    self.assertEqual(123, h.revision)
    self.assertTrue(h.internal_only)

    rows = graph_data.Row.query().fetch()
    self.assertEqual(1, len(rows))

  def testPostHistogram_WithFreshDiagnostics(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])
    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_HISTOGRAM),
        'test_path': test_path,
        'revision': 123,
        'diagnostics': json.dumps([TEST_BENCHMARKS, TEST_OWNERS])
    }
    self.testapp.post('/add_histograms_queue', params)
    histogram_entity = histogram.Histogram.query().fetch()[0]
    hist = histogram_module.Histogram.FromDict(histogram_entity.data)
    self.assertEqual(
        'ec2c0cdc-cd9f-4736-82b4-6ffc3d76e3eb',
        hist.diagnostics[reserved_infos.BENCHMARKS.name].guid)
    self.assertEqual(
        '68e5b3bd-829c-4f4f-be3a-98a94279ccf0',
        hist.diagnostics['owners'].guid)
    telemetry_info_entity = ndb.Key(
        'SparseDiagnostic', TEST_BENCHMARKS['guid']).get()
    ownership_entity = ndb.Key(
        'SparseDiagnostic', TEST_OWNERS['guid']).get()
    self.assertFalse(telemetry_info_entity.internal_only)
    self.assertFalse(ownership_entity.internal_only)

  def testPostHistogram_WithSameDiagnostic(self):
    diag_dict = {
        'guid': '05341937-1272-4214-80ce-43b2d03807f9',
        'values': ['myBenchmark'],
        'type': 'GenericSet',
    }
    diag = histogram.SparseDiagnostic(
        data=diag_dict, start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('Chromium/win7/suite/metric'))
    diag.put()
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])
    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_HISTOGRAM),
        'test_path': test_path,
        'revision': 123,
        'diagnostics': json.dumps([TEST_BENCHMARKS, TEST_OWNERS])
    }
    self.testapp.post('/add_histograms_queue', params)
    histogram_entity = histogram.Histogram.query().fetch()[0]
    hist = histogram_module.Histogram.FromDict(histogram_entity.data)
    self.assertEqual(
        TEST_BENCHMARKS['guid'],
        hist.diagnostics[reserved_infos.BENCHMARKS.name].guid)
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(len(diagnostics), 3)

  def testPostHistogram_WithDifferentDiagnostic(self):
    diag_dict = {
        'guid': 'c397a1a0-e289-45b2-abe7-29e638e09168',
        'values': ['def@chromium.org'],
        'type': 'GenericSet'
    }
    diag = histogram.SparseDiagnostic(
        data=diag_dict, start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('Chromium/win7/suite/metric'))
    diag.put()
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])
    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_HISTOGRAM),
        'test_path': test_path,
        'revision': 123,
        'diagnostics': json.dumps([TEST_BENCHMARKS, TEST_OWNERS])
    }
    self.testapp.post('/add_histograms_queue', params)
    histogram_entity = histogram.Histogram.query().fetch()[0]
    hist = histogram_module.Histogram.FromDict(histogram_entity.data)
    self.assertEqual(
        '68e5b3bd-829c-4f4f-be3a-98a94279ccf0',
        hist.diagnostics['owners'].guid)
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(len(diagnostics), 3)

  def testPostSparseDiagnostic(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])

    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': json.dumps(TEST_BENCHMARKS),
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)

    test = test_key.get()
    self.assertIsNone(test.units)

    original_diagnostic = TEST_BENCHMARKS
    diagnostic_entity = ndb.Key(
        'SparseDiagnostic', original_diagnostic['guid']).get()
    self.assertFalse(diagnostic_entity.internal_only)

  def testPostSparseDiagnostic_Internal(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['mac'])

    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)

    params = {
        'data': json.dumps(TEST_BENCHMARKS),
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test = test_key.get()
    self.assertIsNone(test.units)

    original_diagnostic = TEST_BENCHMARKS
    diagnostic_entity = ndb.Key(
        'SparseDiagnostic', original_diagnostic['guid']).get()
    self.assertTrue(diagnostic_entity.internal_only)

  def testGetUnitArgs_Up(self):
    unit_args = add_histograms_queue.GetUnitArgs('count_biggerIsBetter')
    self.assertEquals(anomaly.UP, unit_args['improvement_direction'])

  def testGetUnitArgs_Down(self):
    unit_args = add_histograms_queue.GetUnitArgs('count_smallerIsBetter')
    self.assertEquals(anomaly.DOWN, unit_args['improvement_direction'])

  def testGetUnitArgs_Unknown(self):
    unit_args = add_histograms_queue.GetUnitArgs('count')
    self.assertEquals(anomaly.UNKNOWN, unit_args['improvement_direction'])

  def testAddRow(self):
    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)
    add_histograms_queue.AddRow(TEST_HISTOGRAM, test_key, 123, test_path, False)

    row = graph_data.Row.query().fetch()[0]
    fields = row.to_dict().iterkeys()
    d_fields = []
    r_fields = []
    for field in fields:
      if field.startswith('d_'):
        d_fields.append(field)
      elif field.startswith('r_'):
        r_fields.append(field)

    self.assertAlmostEqual(2.0, row.value)
    self.assertAlmostEqual(1.0, row.error)
    self.assertFalse(row.internal_only)

    self.assertEqual(4, len(d_fields))
    self.assertEqual(3, row.d_count)
    self.assertAlmostEqual(3.0, row.d_max)
    self.assertAlmostEqual(1.0, row.d_min)
    self.assertAlmostEqual(6.0, row.d_sum)

    self.assertEqual(2, len(r_fields))
    self.assertEqual('4cd34ad3320db114ad3a2bd2acc02aba004d0cb4', row.r_v8_git)
    self.assertEqual('123', row.r_chromium_commit_pos)

  def testAddRow_WithCustomSummaryOptions(self):
    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)

    hist = histogram_module.Histogram.FromDict(TEST_HISTOGRAM)
    hist.CustomizeSummaryOptions({
        'avg': True,
        'std': True,
        'count': True,
        'max': False,
        'min': False,
        'sum': False
        })
    add_histograms_queue.AddRow(hist.AsDict(), test_key, 123, test_path,
                                False)
    row = graph_data.Row.query().fetch()[0]
    fields = row.to_dict().iterkeys()
    d_fields = [field for field in fields if field.startswith('d_')]

    self.assertEqual(1, len(d_fields))
    self.assertEqual(3, row.d_count)

  def testAddRow_SetsInternalOnly(self):
    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)
    add_histograms_queue.AddRow(TEST_HISTOGRAM, test_key, 123, test_path, True)
    row = graph_data.Row.query().fetch()[0]
    self.assertTrue(row.internal_only)

  def testAddRow_DoesntAddRowForEmptyHistogram(self):
    hist = histogram_module.Histogram('foo', 'count').AsDict()
    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)
    add_histograms_queue.AddRow(hist, test_key, 123, test_path, True)

    rows = graph_data.Row.query().fetch()
    self.assertEqual(0, len(rows))

  def testAddRow_FailsWithNonSingularRevisionInfo(self):
    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)
    hist = copy.deepcopy(TEST_HISTOGRAM)
    hist['diagnostics'][reserved_infos.CATAPULT_REVISIONS.name] = {
        'type': 'GenericSet', 'values': [123, 456]}

    with self.assertRaises(add_histograms_queue.BadRequestError):
      add_histograms_queue.AddRow(hist, test_key, 123, test_path, False)
