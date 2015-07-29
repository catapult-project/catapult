# -*- coding: utf-8 -*-
# Copyright 2015 Google Inc. All Rights Reserved.
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
# limitations under the License.
"""Unit tests for tracker_file."""

from gslib.tests.testcase.unit_testcase import GsUtilUnitTestCase
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.tracker_file import _HashFilename
from gslib.tracker_file import DeleteTrackerFile
from gslib.tracker_file import GetRewriteTrackerFilePath
from gslib.tracker_file import HashRewriteParameters
from gslib.tracker_file import ReadRewriteTrackerFile
from gslib.tracker_file import WriteRewriteTrackerFile


class TestTrackerFile(GsUtilUnitTestCase):
  """Unit tests for parallel upload functions in cp command."""

  def test_HashFilename(self):
    # Tests that _HashFilename function works for both string and unicode
    # filenames (without raising any Unicode encode/decode errors).
    _HashFilename('file1')
    _HashFilename(u'file1')

  def test_RewriteTrackerFile(self):
    """Tests Rewrite tracker file functions."""
    tracker_file_name = GetRewriteTrackerFilePath('bk1', 'obj1', 'bk2', 'obj2',
                                                  self.test_api)
    # Should succeed regardless of whether it exists.
    DeleteTrackerFile(tracker_file_name)
    src_obj_metadata = apitools_messages.Object(
        bucket='bk1', name='obj1', etag='etag1', md5Hash='12345')
    src_obj2_metadata = apitools_messages.Object(
        bucket='bk1', name='obj1', etag='etag2', md5Hash='67890')
    dst_obj_metadata = apitools_messages.Object(
        bucket='bk2', name='obj2')
    rewrite_token = 'token1'
    self.assertIsNone(ReadRewriteTrackerFile(tracker_file_name,
                                             src_obj_metadata))
    rewrite_params_hash = HashRewriteParameters(
        src_obj_metadata, dst_obj_metadata, 'full')
    WriteRewriteTrackerFile(tracker_file_name, rewrite_params_hash,
                            rewrite_token)
    self.assertEqual(
        ReadRewriteTrackerFile(tracker_file_name, rewrite_params_hash),
        rewrite_token)

    # Tracker file for an updated source object (with non-matching etag/md5)
    # should return None.
    rewrite_params_hash2 = HashRewriteParameters(
        src_obj2_metadata, dst_obj_metadata, 'full')

    self.assertIsNone(ReadRewriteTrackerFile(tracker_file_name,
                                             rewrite_params_hash2))
    DeleteTrackerFile(tracker_file_name)
    