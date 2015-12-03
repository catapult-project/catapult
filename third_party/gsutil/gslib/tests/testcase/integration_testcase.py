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
"""Contains gsutil base integration test case class."""

from __future__ import absolute_import

from contextlib import contextmanager
import cStringIO
import locale
import logging
import os
import subprocess
import sys
import tempfile

import boto
from boto.exception import StorageResponseError
from boto.s3.deletemarker import DeleteMarker
from boto.storage_uri import BucketStorageUri

import gslib
from gslib.gcs_json_api import GcsJsonApi
from gslib.hashing_helper import Base64ToHexHash
from gslib.project_id import GOOG_PROJ_ID_HDR
from gslib.project_id import PopulateProjectId
from gslib.tests.testcase import base
import gslib.tests.util as util
from gslib.tests.util import ObjectToURI as suri
from gslib.tests.util import RUN_S3_TESTS
from gslib.tests.util import SetBotoConfigFileForTest
from gslib.tests.util import SetBotoConfigForTest
from gslib.tests.util import SetEnvironmentForTest
from gslib.tests.util import unittest
import gslib.third_party.storage_apitools.storage_v1_messages as apitools_messages
from gslib.util import IS_WINDOWS
from gslib.util import Retry
from gslib.util import UTF8


LOGGER = logging.getLogger('integration-test')

# Contents of boto config file that will tell gsutil not to override the real
# error message with a warning about anonymous access if no credentials are
# provided in the config file. Also, because we retry 401s, reduce the number
# of retries so we don't go through a long exponential backoff in tests.
BOTO_CONFIG_CONTENTS_IGNORE_ANON_WARNING = """
[Boto]
num_retries = 2
[Tests]
bypass_anonymous_access_warning = True
"""


def SkipForGS(reason):
  if not RUN_S3_TESTS:
    return unittest.skip(reason)
  else:
    return lambda func: func


def SkipForS3(reason):
  if RUN_S3_TESTS:
    return unittest.skip(reason)
  else:
    return lambda func: func


# TODO: Right now, most tests use the XML API. Instead, they should respect
# prefer_api in the same way that commands do.
@unittest.skipUnless(util.RUN_INTEGRATION_TESTS,
                     'Not running integration tests.')
class GsUtilIntegrationTestCase(base.GsUtilTestCase):
  """Base class for gsutil integration tests."""
  GROUP_TEST_ADDRESS = 'gs-discussion@googlegroups.com'
  GROUP_TEST_ID = (
      '00b4903a97d097895ab58ef505d535916a712215b79c3e54932c2eb502ad97f5')
  USER_TEST_ADDRESS = 'gsutiltestuser@gmail.com'
  USER_TEST_ID = (
      '00b4903a97b201e40d2a5a3ddfe044bb1ab79c75b2e817cbe350297eccc81c84')
  DOMAIN_TEST = 'google.com'
  # No one can create this bucket without owning the gmail.com domain, and we
  # won't create this bucket, so it shouldn't exist.
  # It would be nice to use google.com here but JSON API disallows
  # 'google' in resource IDs.
  nonexistent_bucket_name = 'nonexistent-bucket-foobar.gmail.com'

  def setUp(self):
    """Creates base configuration for integration tests."""
    super(GsUtilIntegrationTestCase, self).setUp()
    self.bucket_uris = []

    # Set up API version and project ID handler.
    self.api_version = boto.config.get_value(
        'GSUtil', 'default_api_version', '1')

    # Instantiate a JSON API for use by the current integration test.
    self.json_api = GcsJsonApi(BucketStorageUri, logging.getLogger(),
                               'gs')

    if util.RUN_S3_TESTS:
      self.nonexistent_bucket_name = (
          'nonexistentbucket-asf801rj3r9as90mfnnkjxpo02')

  # Retry with an exponential backoff if a server error is received. This
  # ensures that we try *really* hard to clean up after ourselves.
  # TODO: As long as we're still using boto to do the teardown,
  # we decorate with boto exceptions.  Eventually this should be migrated
  # to CloudApi exceptions.
  @Retry(StorageResponseError, tries=7, timeout_secs=1)
  def tearDown(self):
    super(GsUtilIntegrationTestCase, self).tearDown()

    while self.bucket_uris:
      bucket_uri = self.bucket_uris[-1]
      try:
        bucket_list = self._ListBucket(bucket_uri)
      except StorageResponseError, e:
        # This can happen for tests of rm -r command, which for bucket-only
        # URIs delete the bucket at the end.
        if e.status == 404:
          self.bucket_uris.pop()
          continue
        else:
          raise
      while bucket_list:
        error = None
        for k in bucket_list:
          try:
            if isinstance(k, DeleteMarker):
              bucket_uri.get_bucket().delete_key(k.name,
                                                 version_id=k.version_id)
            else:
              k.delete()
          except StorageResponseError, e:
            # This could happen if objects that have already been deleted are
            # still showing up in the listing due to eventual consistency. In
            # that case, we continue on until we've tried to deleted every
            # object in the listing before raising the error on which to retry.
            if e.status == 404:
              error = e
            else:
              raise
        if error:
          raise error  # pylint: disable=raising-bad-type
        bucket_list = self._ListBucket(bucket_uri)
      bucket_uri.delete_bucket()
      self.bucket_uris.pop()

  def _ListBucket(self, bucket_uri):
    if bucket_uri.scheme == 's3':
      # storage_uri will omit delete markers from bucket listings, but
      # these must be deleted before we can remove an S3 bucket.
      return list(v for v in bucket_uri.get_bucket().list_versions())
    return list(bucket_uri.list_bucket(all_versions=True))

  def AssertNObjectsInBucket(self, bucket_uri, num_objects, versioned=False):
    """Checks (with retries) that 'ls bucket_uri/**' returns num_objects.

    This is a common test pattern to deal with eventual listing consistency for
    tests that rely on a set of objects to be listed.

    Args:
      bucket_uri: storage_uri for the bucket.
      num_objects: number of objects expected in the bucket.
      versioned: If True, perform a versioned listing.

    Raises:
      AssertionError if number of objects does not match expected value.

    Returns:
      Listing split across lines.
    """
    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=5, timeout_secs=1)
    def _Check1():
      command = ['ls', '-a'] if versioned else ['ls']
      b_uri = [suri(bucket_uri) + '/**'] if num_objects else [suri(bucket_uri)]
      listing = self.RunGsUtil(command + b_uri, return_stdout=True).split('\n')
      # num_objects + one trailing newline.
      self.assertEquals(len(listing), num_objects + 1)
      return listing
    return _Check1()

  def CreateBucket(self, bucket_name=None, test_objects=0, storage_class=None,
                   provider=None, prefer_json_api=False):
    """Creates a test bucket.

    The bucket and all of its contents will be deleted after the test.

    Args:
      bucket_name: Create the bucket with this name. If not provided, a
                   temporary test bucket name is constructed.
      test_objects: The number of objects that should be placed in the bucket.
                    Defaults to 0.
      storage_class: storage class to use. If not provided we us standard.
      provider: Provider to use - either "gs" (the default) or "s3".
      prefer_json_api: If true, use the JSON creation functions where possible.

    Returns:
      StorageUri for the created bucket.
    """
    if not provider:
      provider = self.default_provider

    if prefer_json_api and provider == 'gs':
      json_bucket = self.CreateBucketJson(bucket_name=bucket_name,
                                          test_objects=test_objects,
                                          storage_class=storage_class)
      bucket_uri = boto.storage_uri(
          'gs://%s' % json_bucket.name.encode(UTF8).lower(),
          suppress_consec_slashes=False)
      self.bucket_uris.append(bucket_uri)
      return bucket_uri

    bucket_name = bucket_name or self.MakeTempName('bucket')

    bucket_uri = boto.storage_uri('%s://%s' % (provider, bucket_name.lower()),
                                  suppress_consec_slashes=False)

    if provider == 'gs':
      # Apply API version and project ID headers if necessary.
      headers = {'x-goog-api-version': self.api_version}
      headers[GOOG_PROJ_ID_HDR] = PopulateProjectId()
    else:
      headers = {}

    # Parallel tests can easily run into bucket creation quotas.
    # Retry with exponential backoff so that we create them as fast as we
    # reasonably can.
    @Retry(StorageResponseError, tries=7, timeout_secs=1)
    def _CreateBucketWithExponentialBackoff():
      bucket_uri.create_bucket(storage_class=storage_class, headers=headers)

    _CreateBucketWithExponentialBackoff()
    self.bucket_uris.append(bucket_uri)
    for i in range(test_objects):
      self.CreateObject(bucket_uri=bucket_uri,
                        object_name=self.MakeTempName('obj'),
                        contents='test %d' % i)
    return bucket_uri

  def CreateVersionedBucket(self, bucket_name=None, test_objects=0):
    """Creates a versioned test bucket.

    The bucket and all of its contents will be deleted after the test.

    Args:
      bucket_name: Create the bucket with this name. If not provided, a
                   temporary test bucket name is constructed.
      test_objects: The number of objects that should be placed in the bucket.
                    Defaults to 0.

    Returns:
      StorageUri for the created bucket with versioning enabled.
    """
    bucket_uri = self.CreateBucket(bucket_name=bucket_name,
                                   test_objects=test_objects)
    bucket_uri.configure_versioning(True)
    return bucket_uri

  def CreateObject(self, bucket_uri=None, object_name=None, contents=None,
                   prefer_json_api=False):
    """Creates a test object.

    Args:
      bucket_uri: The URI of the bucket to place the object in. If not
                  specified, a new temporary bucket is created.
      object_name: The name to use for the object. If not specified, a temporary
                   test object name is constructed.
      contents: The contents to write to the object. If not specified, the key
                is not written to, which means that it isn't actually created
                yet on the server.
      prefer_json_api: If true, use the JSON creation functions where possible.

    Returns:
      A StorageUri for the created object.
    """
    bucket_uri = bucket_uri or self.CreateBucket()

    if prefer_json_api and bucket_uri.scheme == 'gs' and contents:
      object_name = object_name or self.MakeTempName('obj')
      json_object = self.CreateObjectJson(contents=contents,
                                          bucket_name=bucket_uri.bucket_name,
                                          object_name=object_name)
      object_uri = bucket_uri.clone_replace_name(object_name)
      # pylint: disable=protected-access
      # Need to update the StorageUri with the correct values while
      # avoiding creating a versioned string.
      object_uri._update_from_values(None,
                                     json_object.generation,
                                     True,
                                     md5=(Base64ToHexHash(json_object.md5Hash),
                                          json_object.md5Hash.strip('\n"\'')))
      # pylint: enable=protected-access
      return object_uri

    bucket_uri = bucket_uri or self.CreateBucket()
    object_name = object_name or self.MakeTempName('obj')
    key_uri = bucket_uri.clone_replace_name(object_name)
    if contents is not None:
      key_uri.set_contents_from_string(contents)
    return key_uri

  def CreateBucketJson(self, bucket_name=None, test_objects=0,
                       storage_class=None):
    """Creates a test bucket using the JSON API.

    The bucket and all of its contents will be deleted after the test.

    Args:
      bucket_name: Create the bucket with this name. If not provided, a
                   temporary test bucket name is constructed.
      test_objects: The number of objects that should be placed in the bucket.
                    Defaults to 0.
      storage_class: storage class to use. If not provided we us standard.

    Returns:
      Apitools Bucket for the created bucket.
    """
    bucket_name = bucket_name or self.MakeTempName('bucket')
    bucket_metadata = None
    if storage_class:
      bucket_metadata = apitools_messages.Bucket(
          name=bucket_name.lower(),
          storageClass=storage_class)

    # TODO: Add retry and exponential backoff.
    bucket = self.json_api.CreateBucket(bucket_name.lower(),
                                        metadata=bucket_metadata)
    # Add bucket to list of buckets to be cleaned up.
    # TODO: Clean up JSON buckets using JSON API.
    self.bucket_uris.append(
        boto.storage_uri('gs://%s' % (bucket_name.lower()),
                         suppress_consec_slashes=False))
    for i in range(test_objects):
      self.CreateObjectJson(bucket_name=bucket_name,
                            object_name=self.MakeTempName('obj'),
                            contents='test %d' % i)
    return bucket

  def CreateObjectJson(self, contents, bucket_name=None, object_name=None):
    """Creates a test object (GCS provider only) using the JSON API.

    Args:
      contents: The contents to write to the object.
      bucket_name: Name of bucket to place the object in. If not
                   specified, a new temporary bucket is created.
      object_name: The name to use for the object. If not specified, a temporary
                   test object name is constructed.

    Returns:
      An apitools Object for the created object.
    """
    bucket_name = bucket_name or self.CreateBucketJson().name
    object_name = object_name or self.MakeTempName('obj')
    object_metadata = apitools_messages.Object(
        name=object_name,
        bucket=bucket_name,
        contentType='application/octet-stream')
    return self.json_api.UploadObject(cStringIO.StringIO(contents),
                                      object_metadata, provider='gs')

  def RunGsUtil(self, cmd, return_status=False, return_stdout=False,
                return_stderr=False, expected_status=0, stdin=None):
    """Runs the gsutil command.

    Args:
      cmd: The command to run, as a list, e.g. ['cp', 'foo', 'bar']
      return_status: If True, the exit status code is returned.
      return_stdout: If True, the standard output of the command is returned.
      return_stderr: If True, the standard error of the command is returned.
      expected_status: The expected return code. If not specified, defaults to
                       0. If the return code is a different value, an exception
                       is raised.
      stdin: A string of data to pipe to the process as standard input.

    Returns:
      A tuple containing the desired return values specified by the return_*
      arguments.
    """
    cmd = ([gslib.GSUTIL_PATH] + ['--testexceptiontraces'] +
           ['-o', 'GSUtil:default_project_id=' + PopulateProjectId()] +
           cmd)
    if IS_WINDOWS:
      cmd = [sys.executable] + cmd
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE)
    (stdout, stderr) = p.communicate(stdin)
    status = p.returncode

    if expected_status is not None:
      self.assertEqual(
          status, expected_status,
          msg='Expected status %d, got %d.\nCommand:\n%s\n\nstderr:\n%s' % (
              expected_status, status, ' '.join(cmd), stderr))

    toreturn = []
    if return_status:
      toreturn.append(status)
    if return_stdout:
      if IS_WINDOWS:
        stdout = stdout.replace('\r\n', '\n')
      toreturn.append(stdout)
    if return_stderr:
      if IS_WINDOWS:
        stderr = stderr.replace('\r\n', '\n')
      toreturn.append(stderr)

    if len(toreturn) == 1:
      return toreturn[0]
    elif toreturn:
      return tuple(toreturn)

  def RunGsUtilTabCompletion(self, cmd, expected_results=None):
    """Runs the gsutil command in tab completion mode.

    Args:
      cmd: The command to run, as a list, e.g. ['cp', 'foo', 'bar']
      expected_results: The expected tab completion results for the given input.
    """
    cmd = [gslib.GSUTIL_PATH] + ['--testexceptiontraces'] + cmd
    cmd_str = ' '.join(cmd)

    @Retry(AssertionError, tries=5, timeout_secs=1)
    def _RunTabCompletion():
      """Runs the tab completion operation with retries."""
      results_string = None
      with tempfile.NamedTemporaryFile(
          delete=False) as tab_complete_result_file:
        # argcomplete returns results via the '8' file descriptor so we
        # redirect to a file so we can capture them.
        cmd_str_with_result_redirect = '%s 8>%s' % (
            cmd_str, tab_complete_result_file.name)
        env = os.environ.copy()
        env['_ARGCOMPLETE'] = '1'
        env['COMP_LINE'] = cmd_str
        env['COMP_POINT'] = str(len(cmd_str))
        subprocess.call(cmd_str_with_result_redirect, env=env, shell=True)
        results_string = tab_complete_result_file.read().decode(
            locale.getpreferredencoding())
      if results_string:
        results = results_string.split('\013')
      else:
        results = []
      self.assertEqual(results, expected_results)

    # When tests are run in parallel, tab completion could take a long time,
    # so choose a long timeout value.
    with SetBotoConfigForTest([('GSUtil', 'tab_completion_timeout', '120')]):
      _RunTabCompletion()

  @contextmanager
  def SetAnonymousBotoCreds(self):
    boto_config_path = self.CreateTempFile(
        contents=BOTO_CONFIG_CONTENTS_IGNORE_ANON_WARNING)
    with SetBotoConfigFileForTest(boto_config_path):
      # Make sure to reset Developer Shell credential port so that the child
      # gsutil process is really anonymous.
      with SetEnvironmentForTest({'DEVSHELL_CLIENT_PORT': None}):
        yield
