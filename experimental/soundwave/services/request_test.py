# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle
import unittest

import httplib2
import mock

from services import request


def Response(code, content):
  return httplib2.Response({'status': str(code)}), content


class TestRequest(unittest.TestCase):
  def setUp(self):
    self.http = mock.Mock()
    mock.patch('httplib2.Http', return_value=self.http).start()
    mock.patch('time.sleep').start()

  def tearDown(self):
    mock.patch.stopall()

  def testRequest_simple(self):
    self.http.request.return_value = Response(200, 'OK!')
    self.assertEqual(request.Request('http://example.com/'), 'OK!')
    self.http.request.assert_called_once_with(
        'http://example.com/', method='POST', headers=mock.ANY)

  def testRequest_withParams(self):
    self.http.request.return_value = Response(200, 'OK!')
    self.assertEqual(request.Request(
        'http://example.com/', params={'q': 'foo'}), 'OK!')
    self.http.request.assert_called_once_with(
        'http://example.com/?q=foo', method='POST', headers=mock.ANY)

  def testRequest_retryOnServerError(self):
    self.http.request.side_effect = [
        Response(500, 'Oops. Something went wrong!'),
        Response(200, 'All is now OK.')
    ]
    self.assertEqual(request.Request('http://example.com/'), 'All is now OK.')

  def testRequest_failOnClientError(self):
    self.http.request.side_effect = [
        Response(400, 'Bad request!'),
        Response(200, 'This is not called.')
    ]
    with self.assertRaises(request.ClientError):
      request.Request('http://example.com/')


class TestRequestErrors(unittest.TestCase):
  def testClientErrorPickleable(self):
    error = request.ClientError(
        'api', *Response(400, 'You made a bad request!'))
    error = pickle.loads(pickle.dumps(error))
    self.assertIsInstance(error, request.ClientError)
    self.assertEqual(error.request, 'api')
    self.assertEqual(error.response.status, 400)
    self.assertEqual(error.content, 'You made a bad request!')

  def testServerErrorPickleable(self):
    error = request.ServerError(
        'api', *Response(500, 'Oops, I had a problem!'))
    error = pickle.loads(pickle.dumps(error))
    self.assertIsInstance(error, request.ServerError)
    self.assertEqual(error.request, 'api')
    self.assertEqual(error.response.status, 500)
    self.assertEqual(error.content, 'Oops, I had a problem!')
