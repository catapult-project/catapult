# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock

import webapp2
import webtest

from dashboard import pinpoint_request
from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.services import pinpoint_service


class PinpointNewRequestHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(PinpointNewRequestHandlerTest, self).setUp()

    app = webapp2.WSGIApplication(
        [(r'/pinpoint/new', pinpoint_request.PinpointNewRequestHandler)])
    self.testapp = webtest.TestApp(app)

    self.SetCurrentUser('foo@chromium.org')

    namespaced_stored_object.Set('bot_dimensions_map', {
        'mac': [
            {'key': 'foo', 'value': 'mac_dimensions'}
        ],
        'android-webview-nexus5x': [
            {'key': 'foo', 'value': 'android_dimensions'}
        ]
    })

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
  def testPinpointParams_BotUndefined_ReturnsError(self):
    params = {
        'test_path': 'ChromiumPerf/foo/blah/foo'
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_NonTelemetry(self):
    params = {
        'test_path': 'ChromiumPerf/mac/cc_perftests/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'chromium',
        'end_repository': 'chromium',
        'bug_id': 1,
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('cc_perftests', results['target'])
    self.assertEqual('foo@chromium.org', results['email'])
    self.assertEqual('chromium', results['start_repository'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('chromium', results['end_repository'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('1', results['auto_explore'])
    self.assertEqual(1, results['bug_id'])
    self.assertEqual(
        [{'key': 'foo', 'value': 'mac_dimensions'}],
        json.loads(results['dimensions']))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_Telemetry(self):
    params = {
        'test_path': 'ChromiumPerf/mac/system_health/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'chromium',
        'end_repository': 'chromium',
        'bug_id': 1,
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('telemetry_perf_tests', results['target'])
    self.assertEqual('foo@chromium.org', results['email'])
    self.assertEqual('chromium', results['start_repository'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('chromium', results['end_repository'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('1', results['auto_explore'])
    self.assertEqual(1, results['bug_id'])
    self.assertEqual(
        [{'key': 'foo', 'value': 'mac_dimensions'}],
        json.loads(results['dimensions']))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_IsolateTarget_WebviewTelemetry(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'chromium',
        'end_repository': 'chromium',
        'bug_id': 1
    }
    results = pinpoint_request.PinpointParamsFromBisectParams(params)

    self.assertEqual('telemetry_perf_webview_tests', results['target'])
    self.assertEqual('foo@chromium.org', results['email'])
    self.assertEqual('chromium', results['start_repository'])
    self.assertEqual('abcd1234', results['start_git_hash'])
    self.assertEqual('chromium', results['end_repository'])
    self.assertEqual('efgh5678', results['end_git_hash'])
    self.assertEqual('1', results['auto_explore'])
    self.assertEqual(1, results['bug_id'])
    self.assertEqual(
        [{'key': 'foo', 'value': 'android_dimensions'}],
        json.loads(results['dimensions']))

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_StartRepositoryInvalid_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'foo',
        'end_repository': 'chromium',
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_StartRepositoryNoChromium_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'v8',
        'end_repository': 'chromium',
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)

  @mock.patch.object(
      utils, 'IsValidSheriffUser', mock.MagicMock(return_value=True))
  def testPinpointParams_EndRepositoryNoChromium_RaisesError(self):
    params = {
        'test_path': 'ChromiumPerf/android-webview-nexus5x/system_health/foo',
        'start_git_hash': 'abcd1234',
        'end_git_hash': 'efgh5678',
        'start_repository': 'chromium',
        'end_repository': 'v8',
    }
    with self.assertRaises(pinpoint_request.InvalidParamsError):
      pinpoint_request.PinpointParamsFromBisectParams(params)
