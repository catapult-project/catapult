# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import urlparse
import webapp2
import webtest

from dashboard import add_histograms
from dashboard.common import testing_common
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set


class AddHistogramsTest(testing_common.TestCase):
  def setUp(self):
    super(AddHistogramsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms', add_histograms.AddHistogramsHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPostHistogramSetsTestPathAndRevision(self):
    data = json.dumps([
        {
            'benchmarkName': 'benchmark',
            'canonicalUrl': '',
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'label': '',
            'legacyTIRLabel': '',
            'storyDisplayName': 'story',
            'type': 'TelemetryInfo'
        }, {
            'angle': [],
            'catapult': [],
            'chromium': [],
            'chromiumCommitPosition': 424242,
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'skia': [],
            'type': 'RevisionInfo',
            'v8': [],
            'webrtc': []
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': '',
            'displayBotName': 'bot',
            'displayMasterName': 'master',
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'logUri': '',
            'type': 'BuildbotInfo'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                'revisions': '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'type': 'Ownership',
            'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb826',
            'emails': ['alice@chromium.org', 'bob@chromium.org'],
            'component': 'fooBar'}
    ])
    self.testapp.post('/add_histograms', {'data': data})
    tasks = self.GetTaskQueueTasks(add_histograms.TASK_QUEUE_NAME)
    params_by_guid = {}
    for task in tasks:
      params = urlparse.parse_qs(base64.b64decode(task['body']))
      guid = json.loads(params['data'][0])['guid']
      params_by_guid[guid] = params

    self.assertEqual(4, len(params_by_guid))
    self.assertEqual(
        'master/bot/benchmark/foo/story',
        params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']['revision'][0])
    self.assertEqual(
        'master/bot/benchmark',
        params_by_guid['e9c2891d-2b04-413f-8cf4-099827e67626']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['e9c2891d-2b04-413f-8cf4-099827e67626']['revision'][0])
    self.assertEqual(
        'master/bot/benchmark/foo/story',
        params_by_guid['0bc1021b-8107-4db7-bc8c-49d7cf53c5ae']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['0bc1021b-8107-4db7-bc8c-49d7cf53c5ae']['revision'][0])
    self.assertEqual(
        'master/bot/benchmark',
        params_by_guid['eb212e80-db58-4cbd-b331-c2245ecbb826']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['eb212e80-db58-4cbd-b331-c2245ecbb826']['revision'][0])

  def testFindHistogramLevelSparseDiagnostics(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([histogram])
    histograms.AddSharedDiagnostic('foo', histogram_module.Generic('bar'))
    histograms.AddSharedDiagnostic(
        'telemetry', histogram_module.TelemetryInfo())
    diagnostics = add_histograms.FindHistogramLevelSparseDiagnostics(
        histogram.guid, histograms)

    self.assertEqual(1, len(diagnostics))
    self.assertIsInstance(diagnostics[0], histogram_module.TelemetryInfo)

  def testComputeTestPathWithStory(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([histogram])
    telemetry_info = histogram_module.TelemetryInfo()
    telemetry_info.AddInfo({
        'storyDisplayName': 'story',
        'benchmarkName': 'benchmark'
    })
    histograms.AddSharedDiagnostic('telemetry', telemetry_info)
    buildbot_info = histogram_module.BuildbotInfo({
        'displayMasterName': 'master',
        'displayBotName': 'bot'
    })
    histograms.AddSharedDiagnostic('buildbot', buildbot_info)
    histogram = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(histogram.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist/story', test_path)

  def testComputeTestPathWithoutStory(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([histogram])
    telemetry_info = histogram_module.TelemetryInfo()
    telemetry_info.AddInfo({
        'benchmarkName': 'benchmark'
    })
    histograms.AddSharedDiagnostic('telemetry', telemetry_info)
    buildbot_info = histogram_module.BuildbotInfo({
        'displayMasterName': 'master',
        'displayBotName': 'bot'
    })
    histograms.AddSharedDiagnostic('buildbot', buildbot_info)
    histogram = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(histogram.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist', test_path)

  def testComputeRevision(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([histogram])
    revision_info = histogram_module.RevisionInfo({
        'chromiumCommitPosition': 424242
    })
    histograms.AddSharedDiagnostic('revisions', revision_info)
    self.assertEqual(424242, add_histograms.ComputeRevision(histograms))

  def testSparseDiagnosticsAreNotInlined(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([histogram])
    histograms.AddSharedDiagnostic('foo', histogram_module.BuildbotInfo({
        'displayMasterName': 'dmn',
        'displayBotName': 'dbn',
        'buildbotMasterName': 'bbmn',
        'buildbotName': 'bbn',
        'buildNumber': 42,
        'logUri': 'uri',
    }))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertTrue(histogram.diagnostics['foo'].has_guid)
