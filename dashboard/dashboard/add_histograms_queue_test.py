# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2
import webtest

from dashboard import add_histograms_queue
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import histogram



TEST_HISTOGRAM = json.dumps({
    'guid': 'a5dd1360-fed5-4872-9f0e-c1c079b2ae26',
    'binBoundaries': [1, [1, 1000, 20]],
    'name': 'foo',
    'unit': 'count'
})


class AddHistogramsQueueTest(testing_common.TestCase):
  def setUp(self):
    super(AddHistogramsQueueTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms_queue',
         add_histograms_queue.AddHistogramsQueueHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPost(self):
    test_path = 'Chromium/win7/suite/metric'
    params = {
        'data': TEST_HISTOGRAM,
        'test_path': test_path,
        'revision': 123
    }
    test_key = utils.TestKey(test_path)
    self.testapp.post('/add_histograms_queue', params)

    original_histogram = json.loads(TEST_HISTOGRAM)

    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))
    self.assertEqual(original_histogram['guid'], histograms[0].key.id())

    h = histograms[0]
    self.assertEqual(TEST_HISTOGRAM, h.data)
    self.assertEqual(test_key, h.test)
    self.assertEqual(123, h.revision)
