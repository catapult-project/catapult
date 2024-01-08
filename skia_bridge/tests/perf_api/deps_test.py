# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

import base64
import json
import os
import sys
import unittest

from unittest import mock
from pathlib import Path

app_path = Path(__file__).parent.parent.parent
if str(app_path) not in sys.path:
  sys.path.insert(0, str(app_path))

from application import app
from application.perf_api import deps

CHROMIUM_URL = 'https://chromium.googlesource.com/chromium/src'
DEPS_PATH = 'DEPS'

class DepsTest(unittest.TestCase):

  def setUp(self):
    self.client = app.Create().test_client()
    os.environ['DISABLE_METRICS'] = 'True'
    self._test_email = deps.ALLOWED_CLIENTS[len(deps.ALLOWED_CLIENTS)-1]

    http = mock.MagicMock()
    self._request = http.request

    patcher = mock.patch('application.perf_api.clients.gitiles_client.'
                         'google_auth_httplib2.AuthorizedHttp')
    self._service_account_http = patcher.start()
    self._service_account_http.return_value = http
    self.addCleanup(patcher.stop)

  def testMissingRepositoryUrl(self):
    p = 'application.perf_api.deps.auth_helper.AuthorizeBearerToken'
    with mock.patch(p) as auth_mock:
      auth_mock.return_value = True, self._test_email
      response = self.client.get('/deps?git_hash=12345')
      self.assertEqual(response.status_code, 400)

  def testMissingGitHash(self):
    p = 'application.perf_api.deps.auth_helper.AuthorizeBearerToken'
    with mock.patch(p) as auth_mock:
      auth_mock.return_value = True, self._test_email
      response = self.client.get('/deps?repository_url='
                                 'https://chromium.googlesource.com/chromium/src')
      self.assertEqual(response.status_code, 400)

  def testOK(self):
    resp = """
vars = {
  'chromium_git': 'https://chromium.googlesource.com',
  'webrtc_git': 'https://webrtc.googlesource.com',
  'webrtc_rev': 'deadbeef',
}
deps = {
  'src/v8': Var('chromium_git') + '/v8/v8.git' + '@' + 'c092edb',
  'src/third_party/webrtc': {
    'url': '{webrtc_git}/src.git@{webrtc_rev}',
  },
  'src/third_party/intellij': {
    'packages': [{
      'package': 'chromium/third_party/intellij',
      'version': 'version:12.0-cr0',
    }],
    'condition': 'checkout_android',
    'dep_type': 'cipd',
  },
}
    """
    resp = resp.encode('ascii')
    self._request.return_value = ({'status': '200'}, base64.b64encode(resp))

    p = 'application.perf_api.deps.auth_helper.AuthorizeBearerToken'
    with mock.patch(p) as auth_mock:
      auth_mock.return_value = True, self._test_email
      url = ('/deps?repository_url='
             'https://chromium.googlesource.com/chromium/src'
             '&git_hash=12345')
      response = self.client.get(url)

      expected = {
        'https://chromium.googlesource.com/v8/v8': 'c092edb',
        'https://webrtc.googlesource.com/src': 'deadbeef',
      }
      self.assertEqual(response.status_code, 200)
      self.assertEqual(json.loads(response.data), expected)

  def testMalformedDeps(self):
    resp =  """
vars = {
  'chromium_git': 'https://chromium.googlesource.com',
}
deps = {
  'src/v8': Var('chromium_git') + '/v8/v8.git' + '@' + 'c092edb' + '@' + 'foo',
}
    """

    resp = resp.encode('ascii')
    self._request.return_value = ({'status': '200'}, base64.b64encode(resp))

    p = 'application.perf_api.deps.auth_helper.AuthorizeBearerToken'
    with mock.patch(p) as auth_mock:
      auth_mock.return_value = True, self._test_email
      response = self.client.get('/deps?repository_url='
                             'https://chromium.googlesource.com/chromium/src'
                             '&git_hash=12345')
      self.assertEqual(response.status_code, 400)

  def testNoDeps(self):
    resp = ''.encode('ascii')
    self._request.return_value = ({'status': '404'}, base64.b64encode(resp))

    p = 'application.perf_api.deps.auth_helper.AuthorizeBearerToken'
    with mock.patch(p) as auth_mock:
      auth_mock.return_value = True, self._test_email
      response = self.client.get('/deps?repository_url='
                         'https://chromium.googlesource.com/chromium/src'
                         '&git_hash=12345')
      self.assertEqual(response.status_code, 500)


if __name__ == '__main__':
  unittest.main()
