# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
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
from dashboard.models import graph_data
from dashboard.models import histogram
from dashboard.models import sheriff
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import reserved_infos

# pylint: disable=too-many-lines


GOOGLER_USER = users.User(email='authorized@chromium.org',
                          _auth_domain='google.com')

_SAMPLE_HISTOGRAM_END_TO_END = [
    {
        'values': ['benchmark'],
        'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
        'type': 'GenericSet',
    }, {
        'values': [424242],
        'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
        'type': 'GenericSet',
    }, {
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }, {
        'values': ['bot'],
        'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
        'type': 'GenericSet'
    }, {
        'binBoundaries': [1, [1, 1000, 20]],
        'diagnostics': {
            reserved_infos.MASTERS.name:
                'e9c2891d-2b04-413f-8cf4-099827e67626',
            reserved_infos.BOTS.name:
                '53fb5448-9f8d-407a-8891-e7233fe1740f',
            reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                '25f0a111-9bb4-4cea-b0c1-af2609623160',
            reserved_infos.BENCHMARKS.name:
                '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
        },
        'guid': '2a714c36-f4ef-488d-8bee-93c7e3149388',
        'name': 'foo2',
        'running': [3, 3, 0.5972531564093516, 2, 1, 6, 2],
        'sampleValues': [1, 2, 3],
        'unit': 'count'
    }
]


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

  @mock.patch.object(
      add_histograms_queue.graph_revisions, 'AddRowsToCacheAsync')
  @mock.patch.object(add_histograms_queue.find_anomalies, 'ProcessTestsAsync')
  def testPost_Succeeds(self, mock_process_test, mock_graph_revisions):
    data = json.dumps(_SAMPLE_HISTOGRAM_END_TO_END)
    sheriff.Sheriff(
        id='my_sheriff1', email='a@chromium.org', patterns=['*/*/*/foo2']).put()

    self.testapp.post('/add_histograms', {'data': data})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(3, len(diagnostics))
    histograms = histogram.Histogram.query().fetch()
    self.assertEqual(1, len(histograms))

    tests = graph_data.TestMetadata.query().fetch()
    # Verify that an anomaly processing was called.
    mock_process_test.assert_called_once_with([tests[1].key])

    rows = graph_data.Row.query().fetch()
    mock_graph_revisions.assert_called_once_with(rows)

  def _SetupRefTest(self, ref_name):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org', patterns=['*/*/*/*']).put()
    data = copy.deepcopy(_SAMPLE_HISTOGRAM_END_TO_END)
    data[4]['name'] = ref_name
    data = json.dumps(data)
    self.testapp.post('/add_histograms', {'data': data})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

  @mock.patch.object(add_histograms_queue.find_anomalies, 'ProcessTestsAsync')
  def testPost_TestNameEndsWithUnderscoreRef_ProcessTestIsNotCalled(
      self, mock_process_test):
    """Tests that Tests ending with "_ref" aren't analyzed for Anomalies."""
    self._SetupRefTest('abcd_ref')
    mock_process_test.assert_called_once_with([])

  @mock.patch.object(add_histograms_queue.find_anomalies, 'ProcessTestsAsync')
  def testPost_TestNameEndsWithSlashRef_ProcessTestIsNotCalled(
      self, mock_process_test):
    """Tests that leaf tests named ref aren't added to the task queue."""
    self._SetupRefTest('ref')
    mock_process_test.assert_called_once_with([])

  @mock.patch.object(add_histograms_queue.find_anomalies, 'ProcessTestsAsync')
  def testPost_TestNameEndsContainsButDoesntEndWithRef_ProcessTestIsCalled(
      self, mock_process_test):
    self._SetupRefTest('_ref_abcd')
    self.assertTrue(mock_process_test.called)

  @mock.patch.object(
      add_histograms_queue.graph_revisions, 'AddRowsToCacheAsync',
      mock.MagicMock())
  @mock.patch.object(
      add_histograms_queue.find_anomalies, 'ProcessTestsAsync',
      mock.MagicMock())
  def testPost_DeduplicateByName(self):
    def _CreateHistogram(revision, device, owner):
      hists = [histogram_module.Histogram('hist', 'count')]
      histograms = histogram_set.HistogramSet(hists)
      histograms.AddSharedDiagnostic(
          reserved_infos.MASTERS.name,
          histogram_module.GenericSet(['master']))
      histograms.AddSharedDiagnostic(
          reserved_infos.BOTS.name,
          histogram_module.GenericSet(['bot']))
      histograms.AddSharedDiagnostic(
          reserved_infos.CHROMIUM_COMMIT_POSITIONS.name,
          histogram_module.GenericSet([revision]))
      histograms.AddSharedDiagnostic(
          reserved_infos.BENCHMARKS.name,
          histogram_module.GenericSet(['benchmark']))
      histograms.AddSharedDiagnostic(
          reserved_infos.OWNERS.name,
          histogram_module.GenericSet([owner]))
      histograms.AddSharedDiagnostic(
          reserved_infos.DEVICE_IDS.name,
          histogram_module.GenericSet([device]))
      histograms.AddSharedDiagnostic(
          reserved_infos.STORIES.name,
          histogram_module.GenericSet(['story1', 'story2']))
      return histograms

    hs = _CreateHistogram(1111, 'device1', 'owner1')
    self.testapp.post(
        '/add_histograms', {'data': json.dumps(hs.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    # There should be the 4 suite level and 2 histogram level diagnostics
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(6, len(diagnostics))

    hs = _CreateHistogram(1112, 'device1', 'owner1')
    self.testapp.post(
        '/add_histograms', {'data': json.dumps(hs.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    # There should STILL be the 4 suite level and 2 histogram level diagnostics
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(6, len(diagnostics))

    hs = _CreateHistogram(1113, 'device2', 'owner1')
    self.testapp.post(
        '/add_histograms', {'data': json.dumps(hs.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    # There should one additional device diagnostic since that changed
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(7, len(diagnostics))

    hs = _CreateHistogram(1114, 'device2', 'owner2')
    self.testapp.post(
        '/add_histograms', {'data': json.dumps(hs.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    # Now there's an additional owner diagnostic
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(8, len(diagnostics))

    hs = _CreateHistogram(1115, 'device2', 'owner2')
    self.testapp.post(
        '/add_histograms', {'data': json.dumps(hs.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    # No more new diagnostics
    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(8, len(diagnostics))

  @mock.patch.object(
      add_histograms_queue.graph_revisions, 'AddRowsToCacheAsync',
      mock.MagicMock())
  @mock.patch.object(
      add_histograms_queue.find_anomalies, 'ProcessTestsAsync',
      mock.MagicMock())
  def testPost_NamesAreSet(self):
    hists = [histogram_module.Histogram('hist', 'count')]
    histograms = histogram_set.HistogramSet(hists)
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.CHROMIUM_COMMIT_POSITIONS.name,
        histogram_module.GenericSet([12345]))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    histograms.AddSharedDiagnostic(
        reserved_infos.DEVICE_IDS.name,
        histogram_module.GenericSet(['devie_foo']))

    self.testapp.post(
        '/add_histograms', {'data': json.dumps(histograms.AsDicts())})
    self.ExecuteTaskQueueTasks('/add_histograms_queue',
                               add_histograms.TASK_QUEUE_NAME)

    diagnostics = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(4, len(diagnostics))

    # The first 3 are all suite level diagnostics, the last is a histogram
    # level diagnostic.
    names = [
        reserved_infos.MASTERS.name,
        reserved_infos.BOTS.name,
        reserved_infos.BENCHMARKS.name,
        reserved_infos.DEVICE_IDS.name]
    for d in diagnostics:
      self.assertIn(d.name, names)
      names.remove(d.name)


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
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'values': ['story'],
            'guid': 'dc894bd9-0b73-4400-9d95-b21ee371031d',
            'type': 'GenericSet',
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.STORIES.name:
                    'dc894bd9-0b73-4400-9d95-b21ee371031d',
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                reserved_infos.STORIES.name:
                    'dc894bd9-0b73-4400-9d95-b21ee371031d',
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
            'values': ['benchmark'],
            'guid': '876d0fba-1d12-4c00-a7e9-5fed467e19e3',
            'type': 'GenericSet',
        }, {
            'values': ['test'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '876d0fba-1d12-4c00-a7e9-5fed467e19e3',
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.GPUS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '876d0fba-1d12-4c00-a7e9-5fed467e19e3',
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
        ['test'], diagnostics[reserved_infos.GPUS.name]['values'])
    self.assertNotEqual(
        '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
        diagnostics[reserved_infos.GPUS.name]['guid'])

  def testPostHistogram_AddsNewSparseDiagnostic(self):
    diag_dict = {
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }
    diag = histogram.SparseDiagnostic(
        data=diag_dict, start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('master/bot/benchmark'))
    diag.put()
    data = json.dumps([
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
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

    self.assertEqual(4, len(diagnostics))
    self.assertEqual(
        'e9c2891d-2b04-413f-8cf4-099827e67626',
        hist['diagnostics'][reserved_infos.MASTERS.name])

  def testPostHistogram_DeduplicatesSameSparseDiagnostic(self):
    diag_dict = {
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }
    diag = histogram.SparseDiagnostic(
        id='e9c2891d-2b04-413f-8cf4-099827e67626', data=diag_dict,
        start_revision=1, end_revision=sys.maxint,
        test=utils.TestKey('master/bot/benchmark'))
    diag.put()
    data = json.dumps([
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
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

    self.assertEqual(3, len(diagnostics))
    self.assertEqual(
        'e9c2891d-2b04-413f-8cf4-099827e67626',
        hist['diagnostics'][reserved_infos.MASTERS.name])

  def testPostHistogramFailsWithoutHistograms(self):
    data = json.dumps([
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }
    ])
    # TODO: Should be a 400 error,
    self.testapp.post('/add_histograms', {'data': data}, status=200)

  def testPostHistogramFailsWithoutBuildbotInfo(self):
    data = json.dumps([
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet'
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }
    ])
    # TODO: Should be a 400 error,
    self.testapp.post('/add_histograms', {'data': data}, status=200)

  def testPostHistogramFailsWithoutChromiumCommit(self):
    data = json.dumps([
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'}
    ])
    # TODO: Should be a 400 error,
    self.testapp.post('/add_histograms', {'data': data}, status=200)

  def testPostHistogramFailsWithoutBenchmark(self):
    data = json.dumps([
        {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }
    ])
    # TODO: Should be a 400 error,
    self.testapp.post('/add_histograms', {'data': data}, status=200)

  def testPostHistogram_AddsSparseDiagnosticByName(self):
    data = json.dumps([
        {
            'type': 'GenericSet',
            'guid': 'cabb59fe-4bcf-4512-881c-d038c7a80635',
            'values': ['alice@chromium.org']
        },
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet',
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.OWNERS.name:
                    'cabb59fe-4bcf-4512-881c-d038c7a80635',
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
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
    self.assertEqual(4, len(diagnostics))
    self.assertEqual(reserved_infos.BENCHMARKS.name, diagnostics[0].name)
    self.assertEqual(reserved_infos.BOTS.name, diagnostics[1].name)
    self.assertEqual(reserved_infos.OWNERS.name, diagnostics[2].name)
    self.assertEqual(reserved_infos.MASTERS.name, diagnostics[3].name)
    self.assertEqual(['benchmark'], diagnostics[0].data['values'])
    self.assertEqual(['bot'], diagnostics[1].data['values'])
    self.assertEqual(['alice@chromium.org'], diagnostics[2].data['values'])
    self.assertEqual(['master'], diagnostics[3].data['values'])
    self.assertEqual('cabb59fe-4bcf-4512-881c-d038c7a80635', owners_info)

  def testPostHistogram_AddsSparseDiagnosticByName_OnlyOnce(self):
    data = json.dumps([
        {
            'type': 'GenericSet',
            'guid': 'cabb59fe-4bcf-4512-881c-d038c7a80635',
            'values': ['alice@chromium.org']
        },
        {
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet',
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet'
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                reserved_infos.OWNERS.name:
                    'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.OWNERS.name:
                    'cabb59fe-4bcf-4512-881c-d038c7a80635',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            },
            'guid': '5239617a-14d6-4f80-8f75-dafda2ff13b1',
            'name': 'bar',
            'unit': 'count'
        }])

    self.testapp.post('/add_histograms', {'data': data})

    diagnostics = histogram.SparseDiagnostic.query().fetch()

    self.assertEqual(4, len(diagnostics))
    self.assertEqual(reserved_infos.BOTS.name, diagnostics[1].name)
    self.assertNotEqual(reserved_infos.BOTS.name, diagnostics[0].name)

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
            'values': ['benchmark'],
            'guid': '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
            'type': 'GenericSet'
        }, {
            'values': [424242],
            'guid': '25f0a111-9bb4-4cea-b0c1-af2609623160',
            'type': 'GenericSet'
        }, {
            'values': ['master'],
            'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
            'type': 'GenericSet'
        }, {
            'values': ['bot'],
            'guid': '53fb5448-9f8d-407a-8891-e7233fe1740f',
            'type': 'GenericSet'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                reserved_infos.OWNERS.name:
                    'cabb59fe-4bcf-4512-881c-d038c7a80635'
            },
            'guid': '4989617a-14d6-4f80-8f75-dafda2ff13b0',
            'name': 'foo',
            'unit': 'count'
        }, {
            'binBoundaries': [1, [1, 1000, 20]],
            'diagnostics': {
                reserved_infos.MASTERS.name:
                    'e9c2891d-2b04-413f-8cf4-099827e67626',
                reserved_infos.BOTS.name:
                    '53fb5448-9f8d-407a-8891-e7233fe1740f',
                reserved_infos.CHROMIUM_COMMIT_POSITIONS.name:
                    '25f0a111-9bb4-4cea-b0c1-af2609623160',
                reserved_infos.BENCHMARKS.name:
                    '0bc1021b-8107-4db7-bc8c-49d7cf53c5ae',
                reserved_infos.OWNERS.name:
                    '7c5bd92f-4146-411b-9192-248ffc1be92c'
            },
            'guid': 'bda61ae3-0178-43f8-8aec-3ab78b9a2e18',
            'name': 'foo',
            'unit': 'count'
        }])

    # TODO(simonhatch): The endpoint is swallowing all exceptions for now.
    self.testapp.post('/add_histograms', {'data': data})

  def testFindHistogramLevelSparseDiagnostics(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic('foo', histogram_module.GenericSet(['bar']))
    histograms.AddSharedDiagnostic(
        reserved_infos.GPUS.name,
        histogram_module.GenericSet([]))
    diagnostics = add_histograms.FindHistogramLevelSparseDiagnostics(
        hist.guid, histograms)

    self.assertEqual(1, len(diagnostics))
    self.assertIsInstance(
        diagnostics[reserved_infos.GPUS.name], histogram_module.GenericSet)

  def testComputeTestPathWithStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['http://story']))
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist/http___story', test_path)

  def testComputeTestPathWithTIRLabel(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['http://story']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORY_TAGS.name,
        histogram_module.GenericSet(
            ['group:media', 'ignored_tag', 'case:browse']))
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual(
        'master/bot/benchmark/hist/browse_media/http___story', test_path)

  def testComputeTestPathWithoutStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist', test_path)

  def testComputeTestPathWithIsRefWithoutStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    histograms.AddSharedDiagnostic(
        reserved_infos.IS_REFERENCE_BUILD.name,
        histogram_module.GenericSet([True]))
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist/ref', test_path)

  def testComputeTestPathWithIsRefAndStory(self):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.MASTERS.name,
        histogram_module.GenericSet(['master']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BOTS.name,
        histogram_module.GenericSet(['bot']))
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    histograms.AddSharedDiagnostic(
        reserved_infos.STORIES.name,
        histogram_module.GenericSet(['http://story']))
    histograms.AddSharedDiagnostic(
        reserved_infos.IS_REFERENCE_BUILD.name,
        histogram_module.GenericSet([True]))
    hist = histograms.GetFirstHistogram()
    test_path = add_histograms.ComputeTestPath(hist.guid, histograms)
    self.assertEqual('master/bot/benchmark/hist/http___story_ref', test_path)

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
    histograms.AddSharedDiagnostic(
        reserved_infos.BENCHMARKS.name,
        histogram_module.GenericSet(['benchmark']))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertTrue(hist.diagnostics[reserved_infos.BENCHMARKS.name].has_guid)

  @mock.patch('logging.info')
  def testLogDebugInfo_Succeeds(self, mock_log):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    histograms.AddSharedDiagnostic(
        reserved_infos.LOG_URLS.name,
        histogram_module.GenericSet(['http://foo']))
    add_histograms._LogDebugInfo(histograms)
    mock_log.assert_called_once_with('Buildbot URL: %s', "['http://foo']")

  @mock.patch('logging.info')
  def testLogDebugInfo_NoHistograms(self, mock_log):
    histograms = histogram_set.HistogramSet()
    add_histograms._LogDebugInfo(histograms)
    mock_log.assert_called_once_with('No histograms in data.')

  @mock.patch('logging.info')
  def testLogDebugInfo_NoLogUrls(self, mock_log):
    hist = histogram_module.Histogram('hist', 'count')
    histograms = histogram_set.HistogramSet([hist])
    add_histograms._LogDebugInfo(histograms)
    mock_log.assert_called_once_with('No LOG_URLS in data.')

  def testDeduplicateAndPut_Same(self):
    d = {
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, name='masters', test=test_key, start_revision=1,
        end_revision=sys.maxint, id='abc')
    entity.put()
    d2 = d.copy()
    d2['guid'] = 'def'
    entity2 = histogram.SparseDiagnostic(
        data=d2, test=test_key,
        start_revision=2, end_revision=sys.maxint, id='def')
    add_histograms.DeduplicateAndPut([entity2], test_key, 2)
    sparse = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(2, len(sparse))

  def testDeduplicateAndPut_Different(self):
    d = {
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, name='masters', test=test_key, start_revision=1,
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
        'values': ['master'],
        'guid': 'e9c2891d-2b04-413f-8cf4-099827e67626',
        'type': 'GenericSet'
    }
    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=d, test=test_key, start_revision=1,
        end_revision=sys.maxint, id='abc')
    entity.put()
    add_histograms.DeduplicateAndPut([entity], test_key, 1)
    sparse = histogram.SparseDiagnostic.query().fetch()
    self.assertEqual(1, len(sparse))
