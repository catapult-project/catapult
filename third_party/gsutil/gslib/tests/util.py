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

from __future__ import absolute_import

from contextlib import contextmanager
import functools
import os
import pkgutil
import posixpath
import re
import tempfile
import unittest
import urlparse

import boto
import crcmod
import gslib.tests as gslib_tests
from gslib.util import UsingCrcmodExtension

if not hasattr(unittest.TestCase, 'assertIsNone'):
  # external dependency unittest2 required for Python <= 2.6
  import unittest2 as unittest  # pylint: disable=g-import-not-at-top

# Flags for running different types of tests.
RUN_INTEGRATION_TESTS = True
RUN_UNIT_TESTS = True
RUN_S3_TESTS = False

PARALLEL_COMPOSITE_UPLOAD_TEST_CONFIG = '/tmp/.boto.parallel_upload_test_config'


def _HasS3Credentials():
  return (boto.config.get('Credentials', 'aws_access_key_id', None) and
          boto.config.get('Credentials', 'aws_secret_access_key', None))

HAS_S3_CREDS = _HasS3Credentials()


def _HasGSHost():
  return boto.config.get('Credentials', 'gs_host', None) is not None

HAS_GS_HOST = _HasGSHost()


def _UsingJSONApi():
  return boto.config.get('GSUtil', 'prefer_api', 'json').upper() != 'XML'

USING_JSON_API = _UsingJSONApi()


def _ArgcompleteAvailable():
  argcomplete = None
  try:
    # pylint: disable=g-import-not-at-top
    import argcomplete
  except ImportError:
    pass
  return argcomplete is not None

ARGCOMPLETE_AVAILABLE = _ArgcompleteAvailable()


def _NormalizeURI(uri):
  """Normalizes the path component of a URI.

  Args:
    uri: URI to normalize.

  Returns:
    Normalized URI.

  Examples:
    gs://foo//bar -> gs://foo/bar
    gs://foo/./bar -> gs://foo/bar
  """
  # Note: we have to do this dance of changing gs:// to file:// because on
  # Windows, the urlparse function won't work with URL schemes that are not
  # known. urlparse('gs://foo/bar') on Windows turns into:
  #     scheme='gs', netloc='', path='//foo/bar'
  # while on non-Windows platforms, it turns into:
  #     scheme='gs', netloc='foo', path='/bar'
  uri = uri.replace('gs://', 'file://')
  parsed = list(urlparse.urlparse(uri))
  parsed[2] = posixpath.normpath(parsed[2])
  if parsed[2].startswith('//'):
    # The normpath function doesn't change '//foo' -> '/foo' by design.
    parsed[2] = parsed[2][1:]
  unparsed = urlparse.urlunparse(parsed)
  unparsed = unparsed.replace('file://', 'gs://')
  return unparsed


def GenerationFromURI(uri):
  """Returns a the generation for a StorageUri.

  Args:
    uri: boto.storage_uri.StorageURI object to get the URI from.

  Returns:
    Generation string for the URI.
  """
  if not (uri.generation or uri.version_id):
    if uri.scheme == 's3': return 'null'
  return uri.generation or uri.version_id


def ObjectToURI(obj, *suffixes):
  """Returns the storage URI string for a given StorageUri or file object.

  Args:
    obj: The object to get the URI from. Can be a file object, a subclass of
         boto.storage_uri.StorageURI, or a string. If a string, it is assumed to
         be a local on-disk path.
    *suffixes: Suffixes to append. For example, ObjectToUri(bucketuri, 'foo')
               would return the URI for a key name 'foo' inside the given
               bucket.

  Returns:
    Storage URI string.
  """
  if isinstance(obj, file):
    return 'file://%s' % os.path.abspath(os.path.join(obj.name, *suffixes))
  if isinstance(obj, basestring):
    return 'file://%s' % os.path.join(obj, *suffixes)
  uri = obj.uri
  if suffixes:
    uri = _NormalizeURI('/'.join([uri] + list(suffixes)))

  # Storage URIs shouldn't contain a trailing slash.
  if uri.endswith('/'):
    uri = uri[:-1]
  return uri

# The mock storage service comes from the Boto library, but it is not
# distributed with Boto when installed as a package. To get around this, we
# copy the file to gslib/tests/mock_storage_service.py when building the gsutil
# package. Try and import from both places here.
# pylint: disable=g-import-not-at-top
try:
  from gslib.tests import mock_storage_service
except ImportError:
  try:
    from boto.tests.integration.s3 import mock_storage_service
  except ImportError:
    try:
      from tests.integration.s3 import mock_storage_service
    except ImportError:
      import mock_storage_service


class GSMockConnection(mock_storage_service.MockConnection):

  def __init__(self, *args, **kwargs):
    kwargs['provider'] = 'gs'
    self.debug = 0
    super(GSMockConnection, self).__init__(*args, **kwargs)

mock_connection = GSMockConnection()


class GSMockBucketStorageUri(mock_storage_service.MockBucketStorageUri):

  def connect(self, access_key_id=None, secret_access_key=None):
    return mock_connection

  def compose(self, components, headers=None):
    """Dummy implementation to allow parallel uploads with tests."""
    return self.new_key()


TEST_BOTO_REMOVE_SECTION = 'TestRemoveSection'


def _SetBotoConfig(section, name, value, revert_list):
  """Sets boto configuration temporarily for testing.

  SetBotoConfigForTest and SetBotoConfigFileForTest should be called by tests
  instead of this function. Those functions will ensure that the configuration
  is reverted to its original setting using _RevertBotoConfig.

  Args:
    section: Boto config section to set
    name: Boto config name to set
    value: Value to set
    revert_list: List for tracking configs to revert.
  """
  prev_value = boto.config.get(section, name, None)
  if not boto.config.has_section(section):
    revert_list.append((section, TEST_BOTO_REMOVE_SECTION, None))
    boto.config.add_section(section)
  revert_list.append((section, name, prev_value))
  if value is None:
    boto.config.remove_option(section, name)
  else:
    boto.config.set(section, name, value)


def _RevertBotoConfig(revert_list):
  """Reverts boto config modifications made by _SetBotoConfig.

  Args:
    revert_list: List of boto config modifications created by calls to
                 _SetBotoConfig.
  """
  sections_to_remove = []
  for section, name, value in revert_list:
    if value is None:
      if name == TEST_BOTO_REMOVE_SECTION:
        sections_to_remove.append(section)
      else:
        boto.config.remove_option(section, name)
    else:
      boto.config.set(section, name, value)
  for section in sections_to_remove:
    boto.config.remove_section(section)


def SequentialAndParallelTransfer(func):
  """Decorator for tests that perform file to object transfers, or vice versa.

  This forces the test to run once normally, and again with special boto
  config settings that will ensure that the test follows the parallel composite
  upload and/or sliced object download code paths.

  Args:
    func: Function to wrap.

  Returns:
    Wrapped function.
  """
  @functools.wraps(func)
  def Wrapper(*args, **kwargs):
    # Run the test normally once.
    func(*args, **kwargs)

    if not RUN_S3_TESTS and UsingCrcmodExtension(crcmod):
      # Try again, forcing parallel upload and sliced download.
      with SetBotoConfigForTest([
          ('GSUtil', 'parallel_composite_upload_threshold', '1'),
          ('GSUtil', 'sliced_object_download_threshold', '1'),
          ('GSUtil', 'sliced_object_download_max_components', '3'),
          ('GSUtil', 'check_hashes', 'always')]):
        func(*args, **kwargs)

  return Wrapper


@contextmanager
def SetBotoConfigForTest(boto_config_list):
  """Sets the input list of boto configs for the duration of a 'with' clause.

  Args:
    boto_config_list: list of tuples of:
      (boto config section to set, boto config name to set, value to set)

  Yields:
    Once after config is set.
  """
  revert_configs = []
  tmp_filename = None
  try:
    tmp_fd, tmp_filename = tempfile.mkstemp(prefix='gsutil-temp-cfg')
    os.close(tmp_fd)
    for boto_config in boto_config_list:
      _SetBotoConfig(boto_config[0], boto_config[1], boto_config[2],
                     revert_configs)
    with open(tmp_filename, 'w') as tmp_file:
      boto.config.write(tmp_file)

    with SetBotoConfigFileForTest(tmp_filename):
      yield
  finally:
    _RevertBotoConfig(revert_configs)
    if tmp_filename:
      try:
        os.remove(tmp_filename)
      except OSError:
        pass


@contextmanager
def SetEnvironmentForTest(env_variable_dict):
  """Sets OS environment variables for a single test."""

  def _ApplyDictToEnvironment(dict_to_apply):
    for k, v in dict_to_apply.iteritems():
      old_values[k] = os.environ.get(k)
      if v is not None:
        os.environ[k] = v
      elif k in os.environ:
        del os.environ[k]

  old_values = {}
  for k in env_variable_dict:
    old_values[k] = os.environ.get(k)

  try:
    _ApplyDictToEnvironment(env_variable_dict)
    yield
  finally:
    _ApplyDictToEnvironment(old_values)


@contextmanager
def SetBotoConfigFileForTest(boto_config_path):
  """Sets a given file as the boto config file for a single test."""
  # Setup for entering "with" block.
  try:
    old_boto_config_env_variable = os.environ['BOTO_CONFIG']
    boto_config_was_set = True
  except KeyError:
    boto_config_was_set = False
  os.environ['BOTO_CONFIG'] = boto_config_path

  try:
    yield
  finally:
    # Teardown for exiting "with" block.
    if boto_config_was_set:
      os.environ['BOTO_CONFIG'] = old_boto_config_env_variable
    else:
      os.environ.pop('BOTO_CONFIG', None)


def GetTestNames():
  """Returns a list of the names of the test modules in gslib.tests."""
  matcher = re.compile(r'^test_(?P<name>.*)$')
  names = []
  for _, modname, _ in pkgutil.iter_modules(gslib_tests.__path__):
    m = matcher.match(modname)
    if m:
      names.append(m.group('name'))
  return names


@contextmanager
def WorkingDirectory(new_working_directory):
  """Changes the working directory for the duration of a 'with' call.

  Args:
    new_working_directory: The directory to switch to before executing wrapped
      code. A None value indicates that no switching is necessary.

  Yields:
    Once after working directory has been changed.
  """
  prev_working_directory = None
  try:
    prev_working_directory = os.getcwd()
  except OSError:
    # This can happen if the current working directory no longer exists.
    pass

  if new_working_directory:
    os.chdir(new_working_directory)

  try:
    yield
  finally:
    if new_working_directory and prev_working_directory:
      os.chdir(prev_working_directory)
