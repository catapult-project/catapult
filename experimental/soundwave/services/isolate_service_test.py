#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import unittest
import zlib

import mock

from services import isolate_service


def ContentResponse(content):
  return [json.dumps({'content': base64.b64encode(zlib.compress(content))})]


def UrlResponse(url, content):
  return [json.dumps({'url': url}), zlib.compress(content)]


class TestIsolateApi(unittest.TestCase):
  def setUp(self):
    self.mock_credentials = mock.Mock()
    self.mock_request = mock.patch('services.request.Request').start()
    self.api = isolate_service.Api(self.mock_credentials)

  def tearDown(self):
    mock.patch.stopall()

  def testRetrieve_content(self):
    self.mock_request.side_effect = ContentResponse('OK!')
    self.assertEqual(self.api.Retrieve('hash'), 'OK!')

  def testRetrieve_fromUrl(self):
    self.mock_request.side_effect = UrlResponse('http://get/response', 'OK!')
    self.assertEqual(self.api.Retrieve('hash'), 'OK!')

  def testRetrieveCompressed_content(self):
    self.mock_request.side_effect = ContentResponse('OK!')
    self.assertEqual(
        self.api.RetrieveCompressed('hash'), zlib.compress('OK!'))

  def testRetrieveCompressed_fromUrl(self):
    self.mock_request.side_effect = UrlResponse('http://get/response', 'OK!')
    self.assertEqual(
        self.api.RetrieveCompressed('hash'), zlib.compress('OK!'))

  def testRetrieveFile_succeeds(self):
    self.mock_request.side_effect = (
        ContentResponse(json.dumps({'files': {'foo': {'h': 'hash2'}}})) +
        UrlResponse('http://get/file/contents', 'nice!'))

    self.assertEqual(self.api.RetrieveFile('hash1', 'foo'), 'nice!')

  def testRetrieveFile_fails(self):
    self.mock_request.side_effect = (
        ContentResponse(json.dumps({'files': {'foo': {'h': 'hash2'}}})) +
        UrlResponse('http://get/file/contents', 'nice!'))

    with self.assertRaises(KeyError):
      self.api.RetrieveFile('hash1', 'bar')  # File not in isolate.
