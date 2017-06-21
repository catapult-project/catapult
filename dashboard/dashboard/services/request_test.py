# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import unittest

import mock

from dashboard.services import request


class _RequestTest(unittest.TestCase):

  def setUp(self):
    http = mock.MagicMock()
    self._request = http.request

    patcher = mock.patch('dashboard.common.utils.ServiceAccountHttp')
    service_account_http = patcher.start()
    service_account_http.return_value = http
    self.addCleanup(patcher.stop)


class SuccessTest(_RequestTest):

  def testRequest(self):
    self._request.return_value = ({'status': '200'}, 'response')
    response = request.Request('https://example.com')
    self._request.assert_called_once_with('https://example.com', method='GET')
    self.assertEqual(response, 'response')

  def testRequestJson(self):
    self._request.return_value = ({'status': '200'}, '"response"')
    response = request.RequestJson('https://example.com')
    self._request.assert_called_once_with('https://example.com', method='GET')
    self.assertEqual(response, 'response')

  def testRequestWithBodyAndParameters(self):
    self._request.return_value = ({'status': '200'}, 'response')
    response = request.Request('https://example.com', 'POST', body='a string',
                               url_param_1='value_1', url_param_2='value_2')
    self._request.assert_called_once_with(
        'https://example.com?url_param_1=value_1&url_param_2=value_2',
        method='POST', body='"a string"',
        headers={'Content-Type': 'application/json'})
    self.assertEqual(response, 'response')


class FailureAndRetryTest(_RequestTest):

  def testHttpErrorCode(self):
    self._request.return_value = ({'status': '500'}, '')
    with self.assertRaises(httplib.HTTPException):
      request.Request('https://example.com')
    self._request.assert_called_with('https://example.com', method='GET')
    self.assertEqual(self._request.call_count, 2)

  def testHttpException(self):
    self._request.side_effect = httplib.HTTPException
    with self.assertRaises(httplib.HTTPException):
      request.Request('https://example.com')
    self._request.assert_called_with('https://example.com', method='GET')
    self.assertEqual(self._request.call_count, 2)

  def testHttpErrorCodeSuccessOnRetry(self):
    failure_return_value = ({'status': '500'}, '')
    success_return_value = ({'status': '200'}, 'response')
    self._request.side_effect = failure_return_value, success_return_value
    response = request.Request('https://example.com')

    self._request.assert_called_with('https://example.com', method='GET')
    self.assertEqual(self._request.call_count, 2)
    self.assertEqual(response, 'response')

  def testHttpExceptionSuccessOnRetry(self):
    return_value = ({'status': '200'}, 'response')
    self._request.side_effect = httplib.HTTPException, return_value
    response = request.Request('https://example.com')

    self._request.assert_called_with('https://example.com', method='GET')
    self.assertEqual(self._request.call_count, 2)
    self.assertEqual(response, 'response')
