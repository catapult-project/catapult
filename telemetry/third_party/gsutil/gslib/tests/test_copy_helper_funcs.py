# -*- coding: utf-8 -*-
# Copyright 2013 Google Inc. All Rights Reserved.
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
"""Unit tests for parallel upload functions in copy_helper."""

from apitools.base.py import exceptions as apitools_exceptions

from util import GSMockBucketStorageUri

from gslib.cloud_api import ResumableUploadAbortException
from gslib.cloud_api import ResumableUploadException
from gslib.cloud_api import ResumableUploadStartOverException
from gslib.cloud_api import ServiceException
from gslib.command import CreateGsutilLogger
from gslib.copy_helper import _AppendComponentTrackerToParallelUploadTrackerFile
from gslib.copy_helper import _CreateParallelUploadTrackerFile
from gslib.copy_helper import _GetPartitionInfo
from gslib.copy_helper import _ParseParallelUploadTrackerFile
from gslib.copy_helper import FilterExistingComponents
from gslib.copy_helper import ObjectFromTracker
from gslib.copy_helper import PerformParallelUploadFileToObjectArgs
from gslib.gcs_json_api import GcsJsonApi
from gslib.hashing_helper import CalculateB64EncodedMd5FromContents
from gslib.storage_url import StorageUrlFromString
from gslib.tests.mock_cloud_api import MockCloudApi
from gslib.tests.testcase.unit_testcase import GsUtilUnitTestCase
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.util import CreateLock


class TestCpFuncs(GsUtilUnitTestCase):
  """Unit tests for parallel upload functions in cp command."""

  def test_GetPartitionInfo(self):
    """Tests the _GetPartitionInfo function."""
    # Simplest case - threshold divides file_size.
    (num_components, component_size) = _GetPartitionInfo(300, 200, 10)
    self.assertEqual(30, num_components)
    self.assertEqual(10, component_size)

    # Threshold = 1 (mod file_size).
    (num_components, component_size) = _GetPartitionInfo(301, 200, 10)
    self.assertEqual(31, num_components)
    self.assertEqual(10, component_size)

    # Threshold = -1 (mod file_size).
    (num_components, component_size) = _GetPartitionInfo(299, 200, 10)
    self.assertEqual(30, num_components)
    self.assertEqual(10, component_size)

    # Too many components needed.
    (num_components, component_size) = _GetPartitionInfo(301, 2, 10)
    self.assertEqual(2, num_components)
    self.assertEqual(151, component_size)

    # Test num_components with huge numbers.
    (num_components, component_size) = _GetPartitionInfo((10 ** 150) + 1,
                                                         10 ** 200,
                                                         10)
    self.assertEqual((10 ** 149) + 1, num_components)
    self.assertEqual(10, component_size)

    # Test component_size with huge numbers.
    (num_components, component_size) = _GetPartitionInfo((10 ** 150) + 1,
                                                         10,
                                                         10)
    self.assertEqual(10, num_components)
    self.assertEqual((10 ** 149) + 1, component_size)

    # Test component_size > file_size (make sure we get at least two components.
    (num_components, component_size) = _GetPartitionInfo(100, 500, 51)
    self.assertEquals(2, num_components)
    self.assertEqual(50, component_size)

  def test_ParseParallelUploadTrackerFile(self):
    """Tests the _ParseParallelUploadTrackerFile function."""
    tracker_file_lock = CreateLock()
    random_prefix = '123'
    objects = ['obj1', '42', 'obj2', '314159']
    contents = '\n'.join([random_prefix] + objects)
    fpath = self.CreateTempFile(file_name='foo', contents=contents)
    expected_objects = [ObjectFromTracker(objects[2 * i], objects[2 * i + 1])
                        for i in range(0, len(objects) / 2)]
    (actual_prefix, actual_objects) = _ParseParallelUploadTrackerFile(
        fpath, tracker_file_lock)
    self.assertEqual(random_prefix, actual_prefix)
    self.assertEqual(expected_objects, actual_objects)

  def test_ParseEmptyParallelUploadTrackerFile(self):
    """Tests _ParseParallelUploadTrackerFile with an empty tracker file."""
    tracker_file_lock = CreateLock()
    fpath = self.CreateTempFile(file_name='foo', contents='')
    expected_objects = []
    (actual_prefix, actual_objects) = _ParseParallelUploadTrackerFile(
        fpath, tracker_file_lock)
    self.assertEqual(actual_objects, expected_objects)
    self.assertIsNotNone(actual_prefix)

  def test_CreateParallelUploadTrackerFile(self):
    """Tests the _CreateParallelUploadTrackerFile function."""
    tracker_file = self.CreateTempFile(file_name='foo', contents='asdf')
    tracker_file_lock = CreateLock()
    random_prefix = '123'
    objects = ['obj1', '42', 'obj2', '314159']
    expected_contents = [random_prefix] + objects
    objects = [ObjectFromTracker(objects[2 * i], objects[2 * i + 1])
               for i in range(0, len(objects) / 2)]
    _CreateParallelUploadTrackerFile(tracker_file, random_prefix, objects,
                                     tracker_file_lock)
    with open(tracker_file, 'rb') as f:
      lines = f.read().splitlines()
    self.assertEqual(expected_contents, lines)

  def test_AppendComponentTrackerToParallelUploadTrackerFile(self):
    """Tests the _CreateParallelUploadTrackerFile function with append."""
    tracker_file = self.CreateTempFile(file_name='foo', contents='asdf')
    tracker_file_lock = CreateLock()
    random_prefix = '123'
    objects = ['obj1', '42', 'obj2', '314159']
    expected_contents = [random_prefix] + objects
    objects = [ObjectFromTracker(objects[2 * i], objects[2 * i + 1])
               for i in range(0, len(objects) / 2)]
    _CreateParallelUploadTrackerFile(tracker_file, random_prefix, objects,
                                     tracker_file_lock)

    new_object = ['obj2', '1234']
    expected_contents += new_object
    new_object = ObjectFromTracker(new_object[0], new_object[1])
    _AppendComponentTrackerToParallelUploadTrackerFile(tracker_file, new_object,
                                                       tracker_file_lock)
    with open(tracker_file, 'rb') as f:
      lines = f.read().splitlines()
    self.assertEqual(expected_contents, lines)

  def test_FilterExistingComponentsNonVersioned(self):
    """Tests upload with a variety of component states."""
    mock_api = MockCloudApi()
    bucket_name = self.MakeTempName('bucket')
    tracker_file = self.CreateTempFile(file_name='foo', contents='asdf')
    tracker_file_lock = CreateLock()

    # dst_obj_metadata used for passing content-type.
    empty_object = apitools_messages.Object()

    # Already uploaded, contents still match, component still used.
    fpath_uploaded_correctly = self.CreateTempFile(file_name='foo1',
                                                   contents='1')
    fpath_uploaded_correctly_url = StorageUrlFromString(
        str(fpath_uploaded_correctly))
    object_uploaded_correctly_url = StorageUrlFromString('%s://%s/%s' % (
        self.default_provider, bucket_name,
        fpath_uploaded_correctly))
    with open(fpath_uploaded_correctly) as f_in:
      fpath_uploaded_correctly_md5 = CalculateB64EncodedMd5FromContents(f_in)
    mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name=fpath_uploaded_correctly,
                                 md5Hash=fpath_uploaded_correctly_md5),
        contents='1')

    args_uploaded_correctly = PerformParallelUploadFileToObjectArgs(
        fpath_uploaded_correctly, 0, 1, fpath_uploaded_correctly_url,
        object_uploaded_correctly_url, '', empty_object, tracker_file,
        tracker_file_lock)

    # Not yet uploaded, but needed.
    fpath_not_uploaded = self.CreateTempFile(file_name='foo2', contents='2')
    fpath_not_uploaded_url = StorageUrlFromString(str(fpath_not_uploaded))
    object_not_uploaded_url = StorageUrlFromString('%s://%s/%s' % (
        self.default_provider, bucket_name, fpath_not_uploaded))
    args_not_uploaded = PerformParallelUploadFileToObjectArgs(
        fpath_not_uploaded, 0, 1, fpath_not_uploaded_url,
        object_not_uploaded_url, '', empty_object, tracker_file,
        tracker_file_lock)

    # Already uploaded, but contents no longer match. Even though the contents
    # differ, we don't delete this since the bucket is not versioned and it
    # will be overwritten anyway.
    fpath_wrong_contents = self.CreateTempFile(file_name='foo4', contents='4')
    fpath_wrong_contents_url = StorageUrlFromString(str(fpath_wrong_contents))
    object_wrong_contents_url = StorageUrlFromString('%s://%s/%s' % (
        self.default_provider, bucket_name, fpath_wrong_contents))
    with open(self.CreateTempFile(contents='_')) as f_in:
      fpath_wrong_contents_md5 = CalculateB64EncodedMd5FromContents(f_in)
    mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name=fpath_wrong_contents,
                                 md5Hash=fpath_wrong_contents_md5),
        contents='1')

    args_wrong_contents = PerformParallelUploadFileToObjectArgs(
        fpath_wrong_contents, 0, 1, fpath_wrong_contents_url,
        object_wrong_contents_url, '', empty_object, tracker_file,
        tracker_file_lock)

    # Exists in tracker file, but component object no longer exists.
    fpath_remote_deleted = self.CreateTempFile(file_name='foo5', contents='5')
    fpath_remote_deleted_url = StorageUrlFromString(
        str(fpath_remote_deleted))
    args_remote_deleted = PerformParallelUploadFileToObjectArgs(
        fpath_remote_deleted, 0, 1, fpath_remote_deleted_url, '', '',
        empty_object, tracker_file, tracker_file_lock)

    # Exists in tracker file and already uploaded, but no longer needed.
    fpath_no_longer_used = self.CreateTempFile(file_name='foo6', contents='6')
    with open(fpath_no_longer_used) as f_in:
      file_md5 = CalculateB64EncodedMd5FromContents(f_in)
    mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name='foo6', md5Hash=file_md5), contents='6')

    dst_args = {fpath_uploaded_correctly: args_uploaded_correctly,
                fpath_not_uploaded: args_not_uploaded,
                fpath_wrong_contents: args_wrong_contents,
                fpath_remote_deleted: args_remote_deleted}

    existing_components = [ObjectFromTracker(fpath_uploaded_correctly, ''),
                           ObjectFromTracker(fpath_wrong_contents, ''),
                           ObjectFromTracker(fpath_remote_deleted, ''),
                           ObjectFromTracker(fpath_no_longer_used, '')]

    bucket_url = StorageUrlFromString('%s://%s' % (self.default_provider,
                                                   bucket_name))

    (components_to_upload, uploaded_components, existing_objects_to_delete) = (
        FilterExistingComponents(dst_args, existing_components,
                                 bucket_url, mock_api))

    for arg in [args_not_uploaded, args_wrong_contents, args_remote_deleted]:
      self.assertTrue(arg in components_to_upload)
    self.assertEqual(1, len(uploaded_components))
    self.assertEqual(args_uploaded_correctly.dst_url.url_string,
                     uploaded_components[0].url_string)
    self.assertEqual(1, len(existing_objects_to_delete))
    no_longer_used_url = StorageUrlFromString('%s://%s/%s' % (
        self.default_provider, bucket_name, fpath_no_longer_used))
    self.assertEqual(no_longer_used_url.url_string,
                     existing_objects_to_delete[0].url_string)

  def test_FilterExistingComponentsVersioned(self):
    """Tests upload with versionined parallel components."""

    mock_api = MockCloudApi()
    bucket_name = self.MakeTempName('bucket')
    mock_api.MockCreateVersionedBucket(bucket_name)

    # dst_obj_metadata used for passing content-type.
    empty_object = apitools_messages.Object()

    tracker_file = self.CreateTempFile(file_name='foo', contents='asdf')
    tracker_file_lock = CreateLock()

    # Already uploaded, contents still match, component still used.
    fpath_uploaded_correctly = self.CreateTempFile(file_name='foo1',
                                                   contents='1')
    fpath_uploaded_correctly_url = StorageUrlFromString(
        str(fpath_uploaded_correctly))
    with open(fpath_uploaded_correctly) as f_in:
      fpath_uploaded_correctly_md5 = CalculateB64EncodedMd5FromContents(f_in)
    object_uploaded_correctly = mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name=fpath_uploaded_correctly,
                                 md5Hash=fpath_uploaded_correctly_md5),
        contents='1')
    object_uploaded_correctly_url = StorageUrlFromString('%s://%s/%s#%s' % (
        self.default_provider, bucket_name,
        fpath_uploaded_correctly, object_uploaded_correctly.generation))
    args_uploaded_correctly = PerformParallelUploadFileToObjectArgs(
        fpath_uploaded_correctly, 0, 1, fpath_uploaded_correctly_url,
        object_uploaded_correctly_url, object_uploaded_correctly.generation,
        empty_object, tracker_file, tracker_file_lock)

    # Duplicate object name in tracker file, but uploaded correctly.
    fpath_duplicate = fpath_uploaded_correctly
    fpath_duplicate_url = StorageUrlFromString(str(fpath_duplicate))
    duplicate_uploaded_correctly = mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name=fpath_duplicate,
                                 md5Hash=fpath_uploaded_correctly_md5),
        contents='1')
    duplicate_uploaded_correctly_url = StorageUrlFromString('%s://%s/%s#%s' % (
        self.default_provider, bucket_name,
        fpath_uploaded_correctly, duplicate_uploaded_correctly.generation))
    args_duplicate = PerformParallelUploadFileToObjectArgs(
        fpath_duplicate, 0, 1, fpath_duplicate_url,
        duplicate_uploaded_correctly_url,
        duplicate_uploaded_correctly.generation, empty_object, tracker_file,
        tracker_file_lock)

    # Already uploaded, but contents no longer match.
    fpath_wrong_contents = self.CreateTempFile(file_name='foo4', contents='4')
    fpath_wrong_contents_url = StorageUrlFromString(str(fpath_wrong_contents))
    with open(self.CreateTempFile(contents='_')) as f_in:
      fpath_wrong_contents_md5 = CalculateB64EncodedMd5FromContents(f_in)
    object_wrong_contents = mock_api.MockCreateObjectWithMetadata(
        apitools_messages.Object(bucket=bucket_name,
                                 name=fpath_wrong_contents,
                                 md5Hash=fpath_wrong_contents_md5),
        contents='_')
    wrong_contents_url = StorageUrlFromString('%s://%s/%s#%s' % (
        self.default_provider, bucket_name,
        fpath_wrong_contents, object_wrong_contents.generation))
    args_wrong_contents = PerformParallelUploadFileToObjectArgs(
        fpath_wrong_contents, 0, 1, fpath_wrong_contents_url,
        wrong_contents_url, '', empty_object, tracker_file,
        tracker_file_lock)

    dst_args = {fpath_uploaded_correctly: args_uploaded_correctly,
                fpath_wrong_contents: args_wrong_contents}

    existing_components = [
        ObjectFromTracker(fpath_uploaded_correctly,
                          object_uploaded_correctly_url.generation),
        ObjectFromTracker(fpath_duplicate,
                          duplicate_uploaded_correctly_url.generation),
        ObjectFromTracker(fpath_wrong_contents,
                          wrong_contents_url.generation)]

    bucket_url = StorageUrlFromString('%s://%s' % (self.default_provider,
                                                   bucket_name))

    (components_to_upload, uploaded_components, existing_objects_to_delete) = (
        FilterExistingComponents(dst_args, existing_components,
                                 bucket_url, mock_api))

    self.assertEqual([args_wrong_contents], components_to_upload)
    self.assertEqual(args_uploaded_correctly.dst_url.url_string,
                     uploaded_components[0].url_string)
    expected_to_delete = [(args_wrong_contents.dst_url.object_name,
                           args_wrong_contents.dst_url.generation),
                          (args_duplicate.dst_url.object_name,
                           args_duplicate.dst_url.generation)]
    for uri in existing_objects_to_delete:
      self.assertTrue((uri.object_name, uri.generation) in expected_to_delete)
    self.assertEqual(len(expected_to_delete), len(existing_objects_to_delete))

  # pylint: disable=protected-access
  def test_TranslateApitoolsResumableUploadException(self):
    """Tests that _TranslateApitoolsResumableUploadException works correctly."""
    gsutil_api = GcsJsonApi(
        GSMockBucketStorageUri,
        CreateGsutilLogger('copy_test'))

    gsutil_api.http.disable_ssl_certificate_validation = True
    exc = apitools_exceptions.HttpError({'status': 503}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc, ServiceException))

    gsutil_api.http.disable_ssl_certificate_validation = False
    exc = apitools_exceptions.HttpError({'status': 503}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc, ResumableUploadException))

    gsutil_api.http.disable_ssl_certificate_validation = False
    exc = apitools_exceptions.HttpError({'status': 429}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc, ResumableUploadException))

    exc = apitools_exceptions.HttpError({'status': 410}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc,
                               ResumableUploadStartOverException))

    exc = apitools_exceptions.HttpError({'status': 404}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc,
                               ResumableUploadStartOverException))

    exc = apitools_exceptions.HttpError({'status': 401}, None, None)
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc, ResumableUploadAbortException))

    exc = apitools_exceptions.TransferError('Aborting transfer')
    translated_exc = gsutil_api._TranslateApitoolsResumableUploadException(exc)
    self.assertTrue(isinstance(translated_exc, ResumableUploadAbortException))
