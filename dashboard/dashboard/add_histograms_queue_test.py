# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
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


TEST_HISTOGRAM = json.dumps({
    'guid': 'a5dd1360-fed5-4872-9f0e-c1c079b2ae26',
    'binBoundaries': [1, [1, 1000, 20]],
    'name': 'foo',
    'unit': 'count_biggerIsBetter'
})


TEST_SPARSE_DIAGNOSTIC = json.dumps({
    'guid': 'ec2c0cdc-cd9f-4736-82b4-6ffc3d76e3eb',
    'benchmarkName': 'myBenchmark',
    'canonicalUrl': 'myCanonicalUrl',
    'label': 'myLabel',
    'legacyTIRLabel': 'myLegacyTIRLabel',
    'storyDisplayName': 'myStoryDisplayName',
    'type': 'TelemetryInfo'
})


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
        'data': TEST_HISTOGRAM,
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)
    original_histogram = json.loads(TEST_HISTOGRAM)

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
    self.assertEqual(original_histogram['guid'], histograms[0].key.id())

    h = histograms[0]
    self.assertEqual(TEST_HISTOGRAM, h.data)
    self.assertEqual(test_key, h.test)
    self.assertEqual(123, h.revision)
    self.assertFalse(h.internal_only)

  def testPostHistogram_Internal(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['mac'])

    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': TEST_HISTOGRAM,
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)
    original_histogram = json.loads(TEST_HISTOGRAM)

    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))
    self.assertEqual(original_histogram['guid'], histograms[0].key.id())

    h = histograms[0]
    self.assertEqual(TEST_HISTOGRAM, h.data)
    self.assertEqual(test_key, h.test)
    self.assertEqual(123, h.revision)
    self.assertTrue(h.internal_only)

  def testPostSparseDiagnostic(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['win7'])

    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': TEST_SPARSE_DIAGNOSTIC,
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test_key = utils.TestKey(test_path)

    test = test_key.get()
    self.assertIsNone(test.units)

    original_diagnostic = json.loads(TEST_SPARSE_DIAGNOSTIC)
    diagnostic_entity = ndb.Key(
        'SparseDiagnostic', original_diagnostic['guid']).get()
    self.assertFalse(diagnostic_entity.internal_only)

  def testPostSparseDiagnostic_Internal(self):
    stored_object.Set(
        add_point_queue.BOT_WHITELIST_KEY, ['mac'])

    test_path = 'Chromium/win7/suite/metric'
    test_key = utils.TestKey(test_path)

    params = {
        'data': TEST_SPARSE_DIAGNOSTIC,
        'test_path': test_path,
        'revision': 123
    }
    self.testapp.post('/add_histograms_queue', params)

    test = test_key.get()
    self.assertIsNone(test.units)

    original_diagnostic = json.loads(TEST_SPARSE_DIAGNOSTIC)
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
