# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

import mock

from dashboard.common import testing_common
from dashboard.pinpoint import test


class _IsolateTest(test.TestCase):

  def setUp(self):
    super(_IsolateTest, self).setUp()

    patcher = mock.patch('dashboard.services.gitiles_service.CommitInfo')
    self.addCleanup(patcher.stop)
    patcher.start()


@mock.patch('dashboard.services.gitiles_service.CommitInfo',
            mock.MagicMock(side_effect=lambda x, y: {'commit': y}))
class FunctionalityTest(_IsolateTest):

  def testPostAndGet(self):
    testing_common.SetIpWhitelist(['remote_ip'])

    builder_name = 'Mac Builder'
    change = '{"commits": [{"repository": "chromium", "git_hash": "git hash"}]}'
    target = 'telemetry_perf_tests'
    isolate_server = 'https://isolate.server'
    isolate_hash = 'a0c28d99182661887feac644317c94fa18eccbbb'

    params = {
        'builder_name': builder_name,
        'change': change,
        'isolate_server': isolate_server,
        'isolate_map': json.dumps({target: isolate_hash}),
    }
    self.testapp.post('/api/isolate', params, status=200)

    params = {
        'builder_name': builder_name,
        'change': change,
        'target': target,
    }
    response = self.testapp.get('/api/isolate', params, status=200)
    expected_body = json.dumps({
        'isolate_server': isolate_server,
        'isolate_hash': isolate_hash
    })
    self.assertEqual(response.normal_body, expected_body)

  def testGetUnknownIsolate(self):
    params = {
        'builder_name': 'Mac Builder',
        'change':
            '{"commits": [{"repository": "chromium", "git_hash": "hash"}]}',
        'target': 'not a real target',
    }
    self.testapp.get('/api/isolate', params, status=404)

  def testPostPermissionDenied(self):
    testing_common.SetIpWhitelist([])
    self.testapp.post('/api/isolate', status=403)


class ParameterValidationTest(_IsolateTest):

  def testExtraParameter(self):
    params = {
        'builder_name': 'Mac Builder',
        'change':
            '{"commits": [{"repository": "chromium", "git_hash": "hash"}]}',
        'target': 'telemetry_perf_tests',
        'extra_parameter': '',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testMissingParameter(self):
    params = {
        'builder_name': 'Mac Builder',
        'change':
            '{"commits": [{"repository": "chromium", "git_hash": "hash"}]}',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testEmptyParameter(self):
    params = {
        'builder_name': 'Mac Builder',
        'change':
            '{"commits": [{"repository": "chromium", "git_hash": "hash"}]}',
        'target': '',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testBadJson(self):
    params = {
        'builder_name': 'Mac Builder',
        'change': '',
        'target': 'telemetry_perf_tests',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testBadChange(self):
    params = {
        'builder_name': 'Mac Builder',
        'change': '{"commits": [{}]}',
        'target': 'telemetry_perf_tests',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testGetInvalidChangeBecauseOfUnknownRepository(self):
    params = {
        'builder_name': 'Mac Builder',
        'change': '{"commits": [{"repository": "foo", "git_hash": "hash"}]}',
        'target': 'telemetry_perf_tests',
    }
    self.testapp.get('/api/isolate', params, status=400)

  def testPostInvalidChangeBecauseOfUnknownRepository(self):
    testing_common.SetIpWhitelist(['remote_ip'])

    params = {
        'builder_name': 'Mac Builder',
        'change': '{"commits": [{"repository": "foo", "git_hash": "hash"}]}',
        'isolate_map': '{"telemetry_perf_tests": "a0c28d9"}',
    }
    self.testapp.post('/api/isolate', params, status=400)
