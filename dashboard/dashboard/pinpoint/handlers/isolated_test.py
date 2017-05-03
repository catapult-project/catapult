# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
import webapp2
import webtest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.pinpoint.handlers import isolated


class IsolatedTest(unittest.TestCase):

  def setUp(self):
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/isolated', isolated.Isolated),
        webapp2.Route(r'/isolated/<builder_name>/<git_hash>/<target>',
                      isolated.Isolated),
    ])
    self.testapp = webtest.TestApp(app)
    self.testapp.extra_environ.update({'REMOTE_ADDR': 'remote_ip'})

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostAndGet(self, mock_get_ip_whitelist):
    mock_get_ip_whitelist.return_value = {'remote_ip'}

    builder_name = 'Mac Builder'
    git_hash = '044129ba034c4141f4fd4e4bd3d6eb0c89ba0670'
    target = 'telemetry_perf_tests'
    isolated_hash = 'a0c28d99182661887feac644317c94fa18eccbbb'

    params = {
        'builder_name': builder_name,
        'git_hash': git_hash,
        'isolated_map': json.dumps({target: isolated_hash}),
    }
    self.testapp.post('/isolated', params, status=200)

    url = '/isolated/%s/%s/%s' % (builder_name, git_hash, target)
    response = self.testapp.get(url, status=200)
    self.assertEqual(response.normal_body, isolated_hash)

  def testGetUnknownIsolated(self):
    self.testapp.get('/isolated/a/b/c', status=404)

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostPermissionDenied(self, _):
    self.testapp.post('/isolated', status=403)

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostExtraParameter(self, mock_get_ip_whitelist):
    mock_get_ip_whitelist.return_value = {'remote_ip'}

    params = {
        'builder_name': 'Builder',
        'git_hash': 'git hash',
        'isolated_map': '{}',
        'extra_parameters': '',
    }
    self.testapp.post('/isolated', params, status=400)

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostMissingParameter(self, mock_get_ip_whitelist):
    mock_get_ip_whitelist.return_value = {'remote_ip'}

    params = {
        'builder_name': 'Builder',
        'git_hash': 'git hash',
    }
    self.testapp.post('/isolated', params, status=400)

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostEmptyParameter(self, mock_get_ip_whitelist):
    mock_get_ip_whitelist.return_value = {'remote_ip'}

    params = {
        'builder_name': 'Builder',
        'git_hash': 'git hash',
        'isolated_map': '',
    }
    self.testapp.post('/isolated', params, status=400)

  @mock.patch('dashboard.common.utils.GetIpWhitelist')
  def testPostBadJson(self, mock_get_ip_whitelist):
    mock_get_ip_whitelist.return_value = {'remote_ip'}

    params = {
        'builder_name': 'Builder',
        'git_hash': 'git hash',
        'isolated_map': 'this is not valid json',
    }
    self.testapp.post('/isolated', params, status=400)
