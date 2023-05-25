# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc.  All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.   .
"""Unit tests for storage URLs."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import os
import sys

from gslib import storage_url
from gslib.exception import InvalidUrlError
from gslib.tests.testcase import base

from unittest import mock

_UNSUPPORTED_DOUBLE_WILDCARD_WARNING_TEXT = (
    '** behavior is undefined if directly preceeded or followed by'
    ' with characters other than / in the cloud and {} locally.'.format(os.sep))


class TestStorageUrl(base.GsUtilTestCase):
  """Unit tests for storage URLs."""

  def setUp(self):
    super(TestStorageUrl, self).setUp()

  def test_is_file_url_string(self):
    self.assertTrue(storage_url.IsFileUrlString('abc'))
    self.assertTrue(storage_url.IsFileUrlString('file://abc'))
    self.assertFalse(storage_url.IsFileUrlString('gs://abc'))
    self.assertFalse(storage_url.IsFileUrlString('s3://abc'))

  def test_storage_url_from_string(self):
    url = storage_url.StorageUrlFromString('abc')
    self.assertTrue(url.IsFileUrl())
    self.assertEquals('abc', url.object_name)

    url = storage_url.StorageUrlFromString('file://abc/123')
    self.assertTrue(url.IsFileUrl())
    self.assertEquals('abc%s123' % os.sep, url.object_name)

    url = storage_url.StorageUrlFromString('gs://abc/123/456')
    self.assertTrue(url.IsCloudUrl())
    self.assertEquals('abc', url.bucket_name)
    self.assertEquals('123/456', url.object_name)

    url = storage_url.StorageUrlFromString('gs://abc///:/')
    self.assertTrue(url.IsCloudUrl())
    self.assertEquals('abc', url.bucket_name)
    self.assertEquals('//:/', url.object_name)

    url = storage_url.StorageUrlFromString('s3://abc/123/456')
    self.assertTrue(url.IsCloudUrl())
    self.assertEquals('abc', url.bucket_name)
    self.assertEquals('123/456', url.object_name)

  def test_raises_error_for_too_many_slashes_after_scheme(self):
    with self.assertRaises(InvalidUrlError):
      storage_url.StorageUrlFromString('gs:///')

    with self.assertRaises(InvalidUrlError):
      storage_url.StorageUrlFromString('gs://////')

  @mock.patch.object(sys.stderr, 'write', autospec=True)
  def test_does_not_warn_if_supported_double_wildcard(self, mock_stderr):
    storage_url.StorageUrlFromString('**')
    storage_url.StorageUrlFromString('gs://bucket/**')

    storage_url.StorageUrlFromString('**' + os.sep)
    storage_url.StorageUrlFromString('gs://bucket/**/')

    storage_url.StorageUrlFromString(os.sep + '**')
    storage_url.StorageUrlFromString('gs://bucket//**')

    storage_url.StorageUrlFromString(os.sep + '**' + os.sep)

    mock_stderr.assert_not_called()

  @mock.patch.object(sys.stderr, 'write', autospec=True)
  def test_warns_if_unsupported_double_wildcard(self, mock_stderr):
    storage_url.StorageUrlFromString('abc**')
    storage_url.StorageUrlFromString('gs://bucket/object**')

    storage_url.StorageUrlFromString('**abc')
    storage_url.StorageUrlFromString('gs://bucket/**object')

    storage_url.StorageUrlFromString('abc**' + os.sep)
    storage_url.StorageUrlFromString('gs://bucket/object**/')

    storage_url.StorageUrlFromString(os.sep + '**abc')
    storage_url.StorageUrlFromString('gs://bucket//**object')

    storage_url.StorageUrlFromString(os.sep + '**' + os.sep + 'abc**')
    storage_url.StorageUrlFromString('gs://bucket/**/abc**')

    storage_url.StorageUrlFromString('abc**' + os.sep + 'abc')
    storage_url.StorageUrlFromString('gs://bucket/abc**/abc')

    storage_url.StorageUrlFromString(os.sep + 'abc**' + os.sep + '**')
    storage_url.StorageUrlFromString('gs://bucket/abc**/**')

    storage_url.StorageUrlFromString('gs://b**')
    storage_url.StorageUrlFromString('gs://**b')

    mock_stderr.assert_has_calls(
        [mock.call(_UNSUPPORTED_DOUBLE_WILDCARD_WARNING_TEXT)] * 14)
