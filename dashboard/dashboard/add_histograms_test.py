# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import mock
import sys
import urlparse
import webapp2
import webtest

from google.appengine.api import users

from dashboard import add_histograms
from dashboard import add_histograms_queue
from dashboard.api import api_auth
from dashboard.api import api_request_handler
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import histogram
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import reserved_infos


GOOGLER_USER = users.User(email='sullivan@chromium.org',
                          _auth_domain='google.com')


def SetGooglerOAuth(mock_oauth):
  mock_oauth.get_current_user.return_value = GOOGLER_USER
  mock_oauth.get_client_id.return_value = api_auth.OAUTH_CLIENT_ID_WHITELIST[0]


class AddHistogramsEndToEndTest(testing_common.TestCase):

  def setUp(self):
    super(AddHistogramsEndToEndTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms', add_histograms.AddHistogramsHandler),
        ('/add_histograms_queue',
         add_histograms_queue.AddHistogramsQueueHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com', is_admin=True)
    oauth_patcher = mock.patch.object(api_auth, 'oauth')
    self.addCleanup(oauth_patcher.stop)
    mock_oauth = oauth_patcher.start()
    SetGooglerOAuth(mock_oauth)

  def testPostHistogramEndToEnd(self):
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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
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
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '2a714c36-f4ef-488d-8bee-93c7e3149388',
            'name': 'foo2',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(2, len(diagnostics))
    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))

class AddHistogramsTest(testing_common.TestCase):

  def setUp(self):
    super(AddHistogramsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_histograms', add_histograms.AddHistogramsHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com', is_admin=True)
    oauth_patcher = mock.patch.object(api_auth, 'oauth')
    self.addCleanup(oauth_patcher.stop)
    mock_oauth = oauth_patcher.start()
    SetGooglerOAuth(mock_oauth)

  def TaskParamsByGuid(self):
    tasks = self.GetTaskQueueTasks(add_histograms.TASK_QUEUE_NAME)
    params_by_guid = {}
    for task in tasks:
      params = urlparse.parse_qs(base64.b64decode(task['body']))
      guid = json.loads(params['data'][0])['guid']
      params_by_guid[guid] = params
    return params_by_guid

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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
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
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '2a714c36-f4ef-488d-8bee-93c7e3149388',
            'name': 'foo2',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data})
    params_by_guid = self.TaskParamsByGuid()

    self.assertEqual(2, len(params_by_guid))
    self.assertEqual(
        'master/bot/benchmark/foo/story',
        params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']['revision'][0])
    self.assertEqual(
        'master/bot/benchmark/foo2/story',
        params_by_guid['2a714c36-f4ef-488d-8bee-93c7e3149388']['test_path'][0])
    self.assertEqual(
        '424242',
        params_by_guid['2a714c36-f4ef-488d-8bee-93c7e3149388']['revision'][0])

  def testPostHistogramPassesHistogramLevelSparseDiagnostics(self):
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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
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
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '2a714c36-f4ef-488d-8bee-93c7e3149388',
            'name': 'foo2',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data})

    params_by_guid = self.TaskParamsByGuid()
    params = params_by_guid['2a714c36-f4ef-488d-8bee-93c7e3149388']
    diagnostics = json.loads(params['diagnostics'][0])

    self.assertEqual(1, len(diagnostics))
    self.assertEqual(
        '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae', diagnostics[0]['guid'])

  def testPostHistogram_AddsNewSparseDiagnostic(self):
    diag_dict = {
        'buildNumber': 0,
        'buildbotMasterName': '',
        'buildbotName': 'buildbotmaster0',
        'displayBotName': 'bot',
        'displayMasterName': 'master',
        'guid': '6ce177ab-3fdb-44cb-aa8d-9ed49765d810',
        'logUri': '',
        'type': 'BuildbotInfo'
    }
    diag = histogram.SparseDiagnostic(
        data=diag_dict, start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('master/bot/benchmark'))
    diag.put()
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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
            'displayBotName': 'bot',
            'displayMasterName': 'master',
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'logUri': '',
            'type': 'BuildbotInfo'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'}
    ])
    self.testapp.post('/add_histograms', {'data': data})

    diagnostics = histogram.SparseDiagnostic.query().fetch()
    params_by_guid = self.TaskParamsByGuid()
    params = params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']
    hist = json.loads(params['data'][0])
    buildbot_info = hist['diagnostics']['buildbot']

    self.assertEqual(2, len(diagnostics))
    self.assertEqual('e9c2891d-2b04-413f-8cf4-099827e67626', buildbot_info)

  def testPostHistogram_DeduplicatesSameSparseDiagnostic(self):
    diag_dict = {
        'buildNumber': 0,
        'buildbotMasterName': '',
        'buildbotName': 'buildbotmaster',
        'displayBotName': 'bot',
        'displayMasterName': 'master',
        'guid': '6ce177ab-3fdb-44cb-aa8d-9ed49765d810',
        'logUri': '',
        'type': 'BuildbotInfo'
    }
    diag = histogram.SparseDiagnostic(
        id='e9c2891d-2b04-413f-8cf4-099827e67626', data=diag_dict,
        start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('master/bot/benchmark'))
    diag.put()
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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster',
            'displayBotName': 'bot',
            'displayMasterName': 'master',
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'logUri': '',
            'type': 'BuildbotInfo'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data})

    diagnostics = histogram.SparseDiagnostic.query().fetch()
    params_by_guid = self.TaskParamsByGuid()
    params = params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']
    hist = json.loads(params['data'][0])
    buildbot_info = hist['diagnostics']['buildbot']

    self.assertEqual(1, len(diagnostics))
    self.assertEqual('6ce177ab-3fdb-44cb-aa8d-9ed49765d810', buildbot_info)

  def testPostHistogramFailsWithoutHistograms(self):
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
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
            'displayBotName': 'bot',
            'displayMasterName': 'master',
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'logUri': '',
            'type': 'BuildbotInfo'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data}, status=400)

  def testPostHistogramFailsWithoutBuildbotInfo(self):
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
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data}, status=400)

  def testPostHistogramFailsWithoutChromiumCommit(self):
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
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
            'displayBotName': 'bot',
            'displayMasterName': 'master',
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'logUri': '',
            'type': 'BuildbotInfo'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'}
    ])
    self.testapp.post('/add_histograms', {'data': data}, status=400)

  def testPostHistogramFailsWithoutTelemetryInfo(self):
    data = json.dumps([
        {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
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
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }
    ])
    self.testapp.post('/add_histograms', {'data': data}, status=400)

  def testPostHistogram_AddsSparseDiagnosticByName(self):
    data = json.dumps([
        {
            'type': 'GenericSet',
            'guid': 'cabb59fe-4bcf-4512-881c-d038c7a80635',
            'values': ['alice@chromium.org']
        },
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
            'chromiumCommitPosition': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'skia': [],
            'type': 'RevisionInfo',
            'v8': [],
            'webrtc': []
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
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
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                'owners': 'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'}
        ])

    self.testapp.post('/add_histograms', {'data': data})

    diagnostics = histogram.SparseDiagnostic.query().fetch()
    params_by_guid = self.TaskParamsByGuid()

    params = params_by_guid['4989617a-14d6-4f80-8f75-dafda2ff13b0']
    hist = json.loads(params['data'][0])
    owners_info = hist['diagnostics'][reserved_infos.OWNERS.name]
    self.assertEqual(2, len(diagnostics))
    self.assertEqual(reserved_infos.OWNERS.name, diagnostics[0].name)
    self.assertEqual(['alice@chromium.org'], diagnostics[0].data['values'])
    self.assertEqual('cabb59fe-4bcf-4512-881c-d038c7a80635', owners_info)

  def testPostHistogram_AddsSparseDiagnosticByName_OnlyOnce(self):
    data = json.dumps([
        {
            'type': 'GenericSet',
            'guid': 'cabb59fe-4bcf-4512-881c-d038c7a80635',
            'values': ['alice@chromium.org']
        },
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
            'chromiumCommitPosition': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'skia': [],
            'type': 'RevisionInfo',
            'v8': [],
            'webrtc': []
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
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
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                'owners': 'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                'revisions': '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                'owners': 'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '5239617a-14d6-4f80-8f75-dafda2ff13b1',
            'name': 'bar',
            'unit': 'count'
        }])

    self.testapp.post('/add_histograms', {'data': data})

    diagnostics = histogram.SparseDiagnostic.query().fetch()

    self.assertEqual(2, len(diagnostics))
    self.assertEqual(reserved_infos.OWNERS.name, diagnostics[0].name)
    self.assertNotEqual(reserved_infos.OWNERS.name, diagnostics[1].name)

  def testPostHistogram_AddsSparseDiagnosticByName_ErrorsIfDiverging(self):
    data = json.dumps([
        {
            'type': 'GenericSet',
            'guid': 'cabb59fe-4bcf-4512-881c-d038c7a80635',
            'values': ['alice@chromium.org']
        }, {
            'type': 'GenericSet',
            'guid': '7c5bd92f-4146-411b-9192-248ffc1be92c',
            'values': ['bob@chromium.org']
        }, {
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
            'chromiumCommitPosition': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'skia': [],
            'type': 'RevisionInfo',
            'v8': [],
            'webrtc': []
        }, {
            'buildNumber': 0,
            'buildbotMasterName': '',
            'buildbotName': 'buildbotmaster1',
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
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                'owners': 'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                'buildbot': 'e9c2891d-2b04-413f-8cf4-099827e67626',
                'revisions': '25f0a111-9bb4-4cea-b0c1-af2609623160',
                'telemetry': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                'owners': '7c5bd92f-4146-411b-9192-248ffc1be92c'
            },
            'guid': 'bda61ae3-0178-43f8-8aec-3ab78b9a2e18',
            'name': 'foo',
            'unit': 'count'
        }])

    self.assertRaises(
        Exception,
        self.testapp.post, '/add_histograms', {'data': data})

  def testFindHistogramLevelSparseDiagnostics(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic('foo', histogram_module.GenericSet(['bar']))
    histograms.AddSharedDiagnostic(
        'telemetry', histogram_module.TelemetryInfo())
    diagnostics = add_histograms.FindHistogramLevelSparseDiagnostics(
        hist.guid, histograms)

    self.assertEqual(1, len(diagnostics))
    self.assertIsInstance(diagnostics[0], histogram_module.TelemetryInfo)

  def testComputeTestPathWithStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
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
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist/story', test_path)

  def testComputeTestPathWithoutStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
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
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist', test_path)

  def testComputeRevision(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    chromium_commit = histogram_module.GenericSet([424242])
    histograms.AddSharedDiagnostic(
        reserved_infos.CHROMIUM_COMMIT_POSITIONS.name, chromium_commit)
    self.assertEqual(424242, add_histograms.ComputeRevision(histograms))

  def testComputeRevision_RaisesOnError(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    chromium_commit = histogram_module.GenericSet([424242, 0])
    histograms.AddSharedDiagnostic(
        reserved_infos.CHROMIUM_COMMIT_POSITIONS.name, chromium_commit)
    with self.assertRaises(api_request_handler.BadRequestError):
      add_histograms.ComputeRevision(histograms)

  def testSparseDiagnosticsAreNotInlined(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic('foo', histogram_module.BuildbotInfo({
        'displayMasterName': 'dmn',
        'displayBotName': 'dbn',
        'buildbotMasterName': 'bbmn',
        'buildbotName': 'bbn',
        'buildNumber': 42,
        'logUri': 'uri',
    }))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertTrue(hist.diagnostics['foo'].has_guid)

  def testDeduplicateAndPut_Same(self):
    d = {
        'buildNumber': 0,
        'buildbotMasterName': '',
        'buildbotName': '',
        'displayBotName': 'bot',
        'displayMasterName': 'master',
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'logUri': '',
        'type': 'BuildbotInfo'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, test=test_key, start_revision=1,
        end_revision=sys.maxint, id='abc')
    entity.put()
    d2 = d.copy()
    d2['guid'] = 'def'
    entity2 = histogram.SparseDiagnostic(
        data=d2, test=test_key,
        start_revision=2, end_revision=sys.maxint, id='def')
    add_histograms.DeduplicateAndPut([entity2], test_key, 2)
    sparse = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(1, len(sparse))

  def testDeduplicateAndPut_Different(self):
    d = {
        'buildNumber': 0,
        'buildbotMasterName': '',
        'buildbotName': '',
        'displayBotName': 'bot',
        'displayMasterName': 'master',
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'logUri': '',
        'type': 'BuildbotInfo'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, test=test_key, start_revision=1,
        end_revision=sys.maxint, id='abc')
    entity.put()
    d2 = d.copy()
    d2['guid'] = 'def'
    d2['displayBotName'] = 'mac'
    entity2 = histogram.SparseDiagnostic(
        data=d2, test=test_key,
        start_revision=1, end_revision=sys.maxint, id='def')
    add_histograms.DeduplicateAndPut([entity2], test_key, 2)
    sparse = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(2, len(sparse))

  def testDeduplicateAndPut_New(self):
    d = {
        'buildNumber': 0,
        'buildbotMasterName': '',
        'buildbotName': '',
        'displayBotName': 'bot',
        'displayMasterName': 'master',
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'logUri': '',
        'type': 'BuildbotInfo'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, test=test_key, start_revision=1,
        end_revision=sys.maxint, id='abc')
    entity.put()
    add_histograms.DeduplicateAndPut([entity], test_key, 1)
    sparse = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(1, len(sparse))
