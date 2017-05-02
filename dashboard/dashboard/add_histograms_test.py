# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2
import webtest

from dashboard import add_histograms
from dashboard.common import testing_common
from tracing.value import histogram as histogram_module


# TODO(eakuefner): Add TelemetryInfo and RevisionInfo to this once test path/
# revision machinery works.
TEST_HISTOGRAM_SET = json.dumps([
    {
        'guid': 'f3201193-eff3-4249-919c-f720423a6061',
        'type': 'Generic',
        'value': 'baz'
    }, {
        'binBoundaries': [1, [1, 1000, 20]],
        'diagnostics': {
            'bar': 'f3201193-eff3-4249-919c-f720423a6061'
        },
        'guid': '02fd09c7-529f-4a60-8e14-845df1b215d0',
        'name': 'foo',
        'unit': 'count'
    }
])

class AddHistogramsTest(testing_common.TestCase):
  def setUp(self):
    super(AddHistogramsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms', add_histograms.AddHistogramsHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPost(self):
    self.testapp.post(
        '/add_histograms', {'data': TEST_HISTOGRAM_SET})
    tasks = self.GetTaskQueueTasks(add_histograms.TASK_QUEUE_NAME)
    self.assertEqual(2, len(tasks))

  def testSparseDiagnosticsAreNotInlined(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_module.HistogramSet([histogram])
    histograms.AddSharedDiagnostic('foo', histogram_module.BuildbotInfo({
        'displayMasterName': 'dmn',
        'displayBotName': 'dbn',
        'buildbotMasterName': 'bbmn',
        'buildbotName': 'bbn',
        'buildNumber': 42,
        'logUri': 'uri',
    }))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertFalse(histogram.diagnostics['foo'].is_inline)
