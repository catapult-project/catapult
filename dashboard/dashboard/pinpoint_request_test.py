# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import itertools
import json
import mock

import webapp2
import webtest

from dashboard import pinpoint_request
from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.services import pinpoint_service


class PinpointNewPrefillRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(PinpointNewPrefillRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/pinpoint/new/prefill',
          pinpoint_request.PinpointNewPrefillRequestHandler)])
    self.testapp = webtest.TestApp(app)

  def testPost_UsesUnescapedStoryName(self):
    t = graph_data.TestMetadata(id='M/B/S/foo', unescaped_story_name='foo:bar')
    t.put()
    response = self.testapp.post(
        '/pinpoint/new/prefill', {'test_path': 'M/B/S/foo'})
    self.assertEqual(
        {'story_filter': 'foo:bar'}, json.loads(response.body))


class PinpointNewPerfTryRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(PinpointNewPerfTryRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/pinpoint/new',
          pinpoint_request.PinpointNewPerfTryRequestHandler)])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('foo@chromium.org')

    namespaced_stored_object.Set('repositories', {
        'chromium': {'some': 'params'},
        'v8': {'more': 'params'}
    })

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=False))
  def testPost_NotSheriff(self):
    response = self.testapp.post('/pinpoint/new')
    self.assertEqual(
        {u'error': u'User "foo@chromium.org" not authorized.'},
        json.loads(response.body))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(pinpoint_service, 'NewJob')
  @mock.patch.object(
      pinpoint_request, 'PinpointParamsFromPerfTryParams',
      mock.MagicMock(return_value={'test': 'result'}))
  def testPost_Succeeds(self, mock_pinpoint):
    mock_pinpoint.return_value = {'foo': 'bar'}
    self.SetCurrentUser('foo@chromium.org')
    params = {'a': 'b', 'c': 'd'}
    response = self.testapp.post('/pinpoint/new', params)

    expected_args = mock.call({'test': 'result'})
    self.assertEqual([expected_args], mock_pinpoint.call_args_list)
    self.assertEqual({'foo': 'bar'}, json.loads(response.body))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_StoryFilterSet(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': '',
        'story_filter': 'story',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('story', results['story'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_ComparisonMode_Try(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': '',
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('try', results['comparison_mode'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=False))
  def testPinpointParams_InvalidSheriff_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/foo/blah/foo',
        'story_filter': '',
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromPerfTryParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_NonTelemetry_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/mac/cc_perftests/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'story_filter': '',
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromPerfTryParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_VRTests(self):
    params = {
        'test_path': 'ChromiumPerf/mac/xr.static.foo/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': json.dumps(
            ['--extra-trace-args', 'abc,123,foo']),
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('vr_perf_tests', results['target'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_Telemetry(self):
    params = {
        'test_path': 'ChromiumPerf/mac/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': json.dumps(
            ['--extra-trace-args', 'abc,123,foo']),
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('mac', results['configuration'])
    self.assertEqual('system_health', results['benchmark'])
    self.assertEqual('performance_test_suite', results['target'])
    self.assertEqual('foo@chromium.org', results['user'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual(
        ['--extra-trace-args', 'abc,123,foo'],
        json.loads(results['extra_test_args']))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_WebviewTelemetry(self):
    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': '',
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('Android Nexus5X WebView Perf', results['configuration'])
    self.assertEqual('system_health', results['benchmark'])
    self.assertEqual('performance_webview_test_suite', results['target'])
    self.assertEqual('foo@chromium.org', results['user'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  def testPinpointParams_ConvertsCommitsToGitHashes(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': '1234',
        'end_commit': '5678',
        'extra_test_args': '',
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('abcd', results['start_git_hash'])
    self.assertEqual('abcd', results['end_git_hash'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering')
  def testPinpointParams_SkipsConvertingHashes(self, mock_crrev):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'extra_test_args': '',
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertFalse(mock_crrev.called)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering')
  def testPinpointParams_V8(self, mock_crrev):
    mock_crrev.return_value = {'git_sha': 'acbd'}
    params = {
        'test_path': 'internal.client.v8/Pixel2/v8/JSTests/Array/Total',
        'start_commit': '1234',
        'end_commit': '5678',
        'extra_test_args': '',
        'story_filter': '',
    }
    results = pinpoint_request.PinpointParamsFromPerfTryParams(params)

    self.assertEqual('', results['target'])
    mock_crrev.assert_any_call(
        number='1234', numbering_identifier='refs/heads/master',
        numbering_type='COMMIT_POSITION', project='chromium', repo='v8/v8')


@mock.patch.object(
    pinpoint_request, 'FindMagnitudeBetweenCommits',
    mock.MagicMock(return_value=None))
class PinpointNewBisectRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(PinpointNewBisectRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/pinpoint/new',
          pinpoint_request.PinpointNewBisectRequestHandler)])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('foo@chromium.org')

    namespaced_stored_object.Set('repositories', {
        'chromium': {'some': 'params'},
        'v8': {'more': 'params'}
    })

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=False))
  def testPost_NotSheriff(self):
    response = self.testapp.post('/pinpoint/new')
    self.assertEqual(
        {u'error': u'User "foo@chromium.org" not authorized.'},
        json.loads(response.body))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(pinpoint_service, 'NewJob')
  @mock.patch.object(
      pinpoint_request, 'PinpointParamsFromBisectParams',
      mock.MagicMock(return_value={'test': 'result'}))
  def testPost_Succeeds(self, mock_pinpoint):
    mock_pinpoint.return_value = {'foo': 'bar'}
    self.SetCurrentUser('foo@chromium.org')
    params = {'a': 'b', 'c': 'd'}
    response = self.testapp.post('/pinpoint/new', params)

    expected_args = mock.call({'test': 'result'})
    self.assertEqual([expected_args], mock_pinpoint.call_args_list)
    self.assertEqual({'foo': 'bar'}, json.loads(response.body))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=False))
  def testPinpointParams_InvalidSheriff_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/foo/blah/foo'
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(pinpoint_service, 'NewJob')
  @mock.patch.object(
      pinpoint_request, 'PinpointParamsFromBisectParams',
      mock.MagicMock(return_value={'test': 'result'}))
  def testPost_Succeeds_AddsToAlert(self, mock_pinpoint):
    mock_pinpoint.return_value = {'jobId': 'bar'}
    self.SetCurrentUser('foo@chromium.org')

    test_key = utils.TestKey('M/B/S/foo')
    anomaly_entity = anomaly.Anomaly(
        start_revision=1, end_revision=2, test=test_key)
    anomaly_entity.put()

    params = {
        'a': 'b', 'c': 'd',
        'alerts': json.dumps([anomaly_entity.key.urlsafe()])}
    response = self.testapp.post('/pinpoint/new', params)

    expected_args = mock.call({'test': 'result'})
    self.assertEqual([expected_args], mock_pinpoint.call_args_list)
    self.assertEqual({'jobId': 'bar'}, json.loads(response.body))
    self.assertEqual(['bar'], anomaly_entity.pinpoint_bisects)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(pinpoint_service, 'NewJob')
  @mock.patch.object(
      pinpoint_request, 'PinpointParamsFromBisectParams',
      mock.MagicMock(return_value={'test': 'result'}))
  def testPost_Fails_AddsToAlert(self, mock_pinpoint):
    mock_pinpoint.return_value = {'error': 'bar'}
    self.SetCurrentUser('foo@chromium.org')

    test_key = utils.TestKey('M/B/S/foo')
    anomaly_entity = anomaly.Anomaly(
        start_revision=1, end_revision=2, test=test_key)
    anomaly_entity.put()

    params = {
        'a': 'b', 'c': 'd',
        'alerts': json.dumps([anomaly_entity.key.urlsafe()])}
    response = self.testapp.post('/pinpoint/new', params)

    expected_args = mock.call({'test': 'result'})
    self.assertEqual([expected_args], mock_pinpoint.call_args_list)
    self.assertEqual({'error': 'bar'}, json.loads(response.body))
    self.assertEqual([], anomaly_entity.pinpoint_bisects)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_ComparisonMagnitude_Added(self):
    test_key = utils.TestKey('ChromiumPerf/mac/cc_perftests/foo')
    anomaly_entity = anomaly.Anomaly(
        start_revision=1, end_revision=2, test=test_key,
        median_before_anomaly=1, median_after_anomaly=10)
    anomaly_entity.put()

    params = {
        'test_path': 'ChromiumPerf/mac/cc_perftests/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
        'alerts': json.dumps([anomaly_entity.key.urlsafe()])
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual(9, results['comparison_magnitude'])
    self.assertEqual(
        anomaly_entity.key.urlsafe(), json.loads(results['tags'])['alert'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_NonTelemetry(self):
    params = {
        'test_path': 'ChromiumPerf/mac/cc_perftests/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('mac', results['configuration'])
    self.assertEqual('cc_perftests', results['benchmark'])
    self.assertEqual('foo', results['chart'])
    self.assertEqual('cc_perftests', results['target'])
    self.assertEqual('foo@chromium.org', results['user'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('performance', results['comparison_mode'])
    self.assertEqual(1, results['bug_id'])
    self.assertEqual(
        params['test_path'],
        json.loads(results['tags'])['test_path'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_Telemetry(self):
    params = {
        'test_path': 'ChromiumPerf/mac/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'story_filter': 'foo',
        'pin': '',
        'bisect_mode': 'performance',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('mac', results['configuration'])
    self.assertEqual('system_health', results['benchmark'])
    self.assertEqual('foo', results['chart'])
    self.assertEqual('performance_test_suite', results['target'])
    self.assertEqual('foo@chromium.org', results['user'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('performance', results['comparison_mode'])
    self.assertEqual(1, results['bug_id'])
    self.assertEqual('foo', results['story'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_WebviewTelemetry(self):
    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('Android Nexus5X WebView Perf', results['configuration'])
    self.assertEqual('system_health', results['benchmark'])
    self.assertEqual('foo', results['chart'])
    self.assertEqual('performance_webview_test_suite', results['target'])
    self.assertEqual('foo@chromium.org', results['user'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('performance', results['comparison_mode'])
    self.assertEqual(1, results['bug_id'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  def testPinpointParams_OldIsolateTarget_Telemetry(self):
    params = {
        'test_path': 'ChromiumPerf/android-nexus5x/system_health/foo',
        'start_commit': '572200',
        'end_commit': '572300',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('telemetry_perf_tests', results['target'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  def testPinpointParams_OldIsolateTarget_WebviewTelemetry(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': '572200',
        'end_commit': '572300',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('telemetry_perf_webview_tests', results['target'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_Metric_TopLevelOnly(self):
    params = {
        'test_path': 'ChromiumPerf/mac/blink_perf/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('foo', results['chart'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_Metric_ChartAndTrace(self):
    params = {
        'test_path': 'ChromiumPerf/mac/blink_perf/foo/http___bar.html',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(
        id=params['test_path'], unescaped_story_name='http://bar.html')
    t.UpdateSheriff()
    t.put()
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('foo', results['chart'])
    self.assertEqual('http://bar.html', results['trace'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_Metric_TIRLabelChartAndTrace(self):
    params = {
        'test_path': 'ChromiumPerf/mac/blink_perf/foo/label/bar.html',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'],)
    t.UpdateSheriff()
    t.put()
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('label', results['tir_label'])
    self.assertEqual('foo', results['chart'])
    self.assertEqual('bar.html', results['trace'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_BisectMode_Invalid_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/mac/blink_perf/foo/label/bar.html',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'foo',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'],)
    t.UpdateSheriff()
    t.put()
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_BisectMode_Functional(self):
    params = {
        'test_path': 'ChromiumPerf/mac/blink_perf/foo/label/bar.html',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': 1,
        'bisect_mode': 'functional',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'],)
    t.UpdateSheriff()
    t.put()
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('functional', results['comparison_mode'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  def testPinpointParams_ConvertsCommitsToGitHashes(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': '1234',
        'end_commit': '5678',
        'bug_id': '',
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('abcd', results['start_git_hash'])
    self.assertEqual('abcd', results['end_git_hash'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering')
  def testPinpointParams_SkipsConvertingHashes(self, mock_crrev):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': '',
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertFalse(mock_crrev.called)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_SplitsStatistics(self):
    statistic_types = ['avg', 'min', 'max', 'sum', 'std', 'count']

    for s in statistic_types:
      params = {
          'test_path': 'ChromiumPerf/mac/system_health/foo_%s' % s,
          'start_commit': 'abcd1234',
          'end_commit': 'efgh5678',
          'bisect_mode': 'performance',
          'story_filter': '',
          'pin': '',
          'bug_id': -1,
      }
      results = pinpoint_request.PinpointParamsFromBisectParams(params)

      self.assertEqual(s, results['statistic'])
      self.assertEqual('foo', results['chart'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_WithPin(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_commit': 'abcd1234',
        'end_commit': 'efgh5678',
        'bug_id': '',
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': 'https://path/to/patch',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('https://path/to/patch', results['pin'])

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering')
  def testPinpointParams_V8(self, mock_crrev):
    mock_crrev.return_value = {'git_sha': 'acbd'}
    params = {
        'test_path': 'internal.client.v8/Pixel2/v8/JSTests/Array/Total',
        'start_commit': '1234',
        'end_commit': '5678',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': 'https://path/to/patch',
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertNotIn('tir_label', results)
    self.assertNotIn('trace', results)
    self.assertEqual('', results['chart'])
    self.assertEqual('', results['target'])
    mock_crrev.assert_any_call(
        number='1234', numbering_identifier='refs/heads/master',
        numbering_type='COMMIT_POSITION', project='chromium', repo='v8/v8')


class PinpointNewBisectComparisonMagnitude(testing_common.TestCase):

  def setUp(self):
    super(PinpointNewBisectComparisonMagnitude, self).setUp()

    self.SetCurrentUser('foo@chromium.org')

    namespaced_stored_object.Set('repositories', {
        'chromium': {'some': 'params'},
        'v8': {'more': 'params'}
    })

  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_NoAlert(self):
    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': '1051',
        'end_commit': '1151',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'])
    t.put()

    rows = dict(
        itertools.chain(
            zip(
                itertools.islice(itertools.count(1000, 2), 50),
                itertools.repeat({'value': 0.1})),
            zip(
                itertools.islice(itertools.count(1101, 2), 50),
                itertools.repeat({'value': 0.5}))))

    testing_common.AddRows(params['test_path'], rows)
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual(0.4, results['comparison_magnitude'])

  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetCommit')
  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_GitHashes(self, mock_commit):
    def _MockCommit(git_sha):
      if git_sha == 'abc':
        return {'number': 1050}
      else:
        return {'number': 1150}
    mock_commit.side_effect = _MockCommit

    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': 'abc',
        'end_commit': 'def',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'])
    t.put()

    rows = dict(
        itertools.chain(
            zip(
                itertools.islice(itertools.count(1000, 2), 50),
                itertools.repeat({'value': 0.1})),
            zip(
                itertools.islice(itertools.count(1101, 2), 50),
                itertools.repeat({'value': 0.5}))))

    testing_common.AddRows(params['test_path'], rows)
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual(0.4, results['comparison_magnitude'])

  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_NoData(self):
    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': '1050',
        'end_commit': '1150',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    t = graph_data.TestMetadata(id=params['test_path'])
    t.put()

    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertFalse('comparison_magnitude' in results)

  @mock.patch.object(
      pinpoint_request.crrev_service, 'GetNumbering',
      mock.MagicMock(return_value={'git_sha': 'abcd'}))
  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_OverriddenAnomalyConfig(self):
    params = {
        'test_path':
            'ChromiumPerf/Android Nexus5X WebView Perf/system_health/foo',
        'start_commit': '1051',
        'end_commit': '1151',
        'bug_id': 1,
        'bisect_mode': 'performance',
        'story_filter': '',
        'pin': '',
    }
    a = anomaly_config.AnomalyConfig()
    a.config = {'min_segment_size': 1}
    a.patterns = ['*/*/*/*']
    a.put()

    t = graph_data.TestMetadata(id=params['test_path'])
    t.overridden_anomaly_config = a.key
    t.put()

    rows = dict(
        itertools.chain(
            zip(
                itertools.islice(itertools.count(1000, 2), 75),
                itertools.repeat({'value': -100.0})),
            [(1050, {'value': 0.1})],
            zip(
                itertools.islice(itertools.count(1101, 2), 50),
                itertools.repeat({'value': 0.5}))))

    testing_common.AddRows(params['test_path'], rows)
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    # We overrode the anomaly config with a window of 1, and there's only a
    # single row with value 0.1, the rest are 0.0.
    self.assertEqual(0.4, results['comparison_magnitude'])
