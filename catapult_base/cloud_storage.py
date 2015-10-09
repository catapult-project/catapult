# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrappers for gsutil, for basic interaction with Google Cloud Storage."""

import collections
import hashlib
import logging
import os
import stat
import subprocess
import sys

from telemetry.core import util
from telemetry import decorators
from telemetry.internal.util import path


PUBLIC_BUCKET = 'chromium-telemetry'
PARTNER_BUCKET = 'chrome-partner-telemetry'
INTERNAL_BUCKET = 'chrome-telemetry'
TELEMETRY_OUTPUT = 'chrome-telemetry-output'

# Uses ordered dict to make sure that bucket's key-value items are ordered from
# the most open to the most restrictive.
BUCKET_ALIASES = collections.OrderedDict((
    ('public', PUBLIC_BUCKET),
    ('partner', PARTNER_BUCKET),
    ('internal', INTERNAL_BUCKET),
    ('output', TELEMETRY_OUTPUT),
))

BUCKET_ALIAS_NAMES = BUCKET_ALIASES.keys()


_GSUTIL_PATH = os.path.join(path.GetTelemetryDir(), 'third_party', 'gsutilz',
                            'gsutil')

# TODO(tbarzic): A workaround for http://crbug.com/386416 and
#     http://crbug.com/359293. See |_RunCommand|.
_CROS_GSUTIL_HOME_WAR = '/home/chromeos-test/'


class CloudStorageError(Exception):
  @staticmethod
  def _GetConfigInstructions():
    command = _GSUTIL_PATH
    if util.IsRunningOnCrosDevice():
      command = 'HOME=%s %s' % (_CROS_GSUTIL_HOME_WAR, _GSUTIL_PATH)
    return ('To configure your credentials:\n'
            '  1. Run "%s config" and follow its instructions.\n'
            '  2. If you have a @google.com account, use that account.\n'
            '  3. For the project-id, just enter 0.' % command)


class PermissionError(CloudStorageError):
  def __init__(self):
    super(PermissionError, self).__init__(
        'Attempted to access a file from Cloud Storage but you don\'t '
        'have permission. ' + self._GetConfigInstructions())


class CredentialsError(CloudStorageError):
  def __init__(self):
    super(CredentialsError, self).__init__(
        'Attempted to access a file from Cloud Storage but you have no '
        'configured credentials. ' + self._GetConfigInstructions())


class NotFoundError(CloudStorageError):
  pass


class ServerError(CloudStorageError):
  pass


# TODO(tonyg/dtu): Can this be replaced with distutils.spawn.find_executable()?
def _FindExecutableInPath(relative_executable_path, *extra_search_paths):
  search_paths = list(extra_search_paths) + os.environ['PATH'].split(os.pathsep)
  for search_path in search_paths:
    executable_path = os.path.join(search_path, relative_executable_path)
    if path.IsExecutable(executable_path):
      return executable_path
  return None

def _EnsureExecutable(gsutil):
  """chmod +x if gsutil is not executable."""
  st = os.stat(gsutil)
  if not st.st_mode & stat.S_IEXEC:
    os.chmod(gsutil, st.st_mode | stat.S_IEXEC)

def _RunCommand(args):
  # On cros device, as telemetry is running as root, home will be set to /root/,
  # which is not writable. gsutil will attempt to create a download tracker dir
  # in home dir and fail. To avoid this, override HOME dir to something writable
  # when running on cros device.
  #
  # TODO(tbarzic): Figure out a better way to handle gsutil on cros.
  #     http://crbug.com/386416, http://crbug.com/359293.
  gsutil_env = None
  if util.IsRunningOnCrosDevice():
    gsutil_env = os.environ.copy()
    gsutil_env['HOME'] = _CROS_GSUTIL_HOME_WAR

  if os.name == 'nt':
    # If Windows, prepend python. Python scripts aren't directly executable.
    args = [sys.executable, _GSUTIL_PATH] + args
  else:
    # Don't do it on POSIX, in case someone is using a shell script to redirect.
    args = [_GSUTIL_PATH] + args
    _EnsureExecutable(_GSUTIL_PATH)

  gsutil = subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=gsutil_env)
  stdout, stderr = gsutil.communicate()

  if gsutil.returncode:
    if stderr.startswith((
        'You are attempting to access protected data with no configured',
        'Failure: No handler was ready to authenticate.')):
      raise CredentialsError()
    if ('status=403' in stderr or 'status 403' in stderr or
        '403 Forbidden' in stderr):
      raise PermissionError()
    if (stderr.startswith('InvalidUriError') or 'No such object' in stderr or
        'No URLs matched' in stderr or 'One or more URLs matched no' in stderr):
      raise NotFoundError(stderr)
    if '500 Internal Server Error' in stderr:
      raise ServerError(stderr)
    raise CloudStorageError(stderr)

  return stdout


def List(bucket):
  query = 'gs://%s/' % bucket
  stdout = _RunCommand(['ls', query])
  return [url[len(query):] for url in stdout.splitlines()]


def Exists(bucket, remote_path):
  try:
    _RunCommand(['ls', 'gs://%s/%s' % (bucket, remote_path)])
    return True
  except NotFoundError:
    return False


def Move(bucket1, bucket2, remote_path):
  url1 = 'gs://%s/%s' % (bucket1, remote_path)
  url2 = 'gs://%s/%s' % (bucket2, remote_path)
  logging.info('Moving %s to %s' % (url1, url2))
  _RunCommand(['mv', url1, url2])


def Copy(bucket_from, bucket_to, remote_path_from, remote_path_to):
  """Copy a file from one location in CloudStorage to another.

  Args:
      bucket_from: The cloud storage bucket where the file is currently located.
      bucket_to: The cloud storage bucket it is being copied to.
      remote_path_from: The file path where the file is located in bucket_from.
      remote_path_to: The file path it is being copied to in bucket_to.

  It should: cause no changes locally or to the starting file, and will
  overwrite any existing files in the destination location.
  """
  url1 = 'gs://%s/%s' % (bucket_from, remote_path_from)
  url2 = 'gs://%s/%s' % (bucket_to, remote_path_to)
  logging.info('Copying %s to %s' % (url1, url2))
  _RunCommand(['cp', url1, url2])


def Delete(bucket, remote_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Deleting %s' % url)
  _RunCommand(['rm', url])


def Get(bucket, remote_path, local_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Downloading %s to %s' % (url, local_path))
  try:
    _RunCommand(['cp', url, local_path])
  except ServerError:
    logging.info('Cloud Storage server error, retrying download')
    _RunCommand(['cp', url, local_path])


def Insert(bucket, remote_path, local_path, publicly_readable=False):
  """ Upload file in |local_path| to cloud storage.
  Args:
    bucket: the google cloud storage bucket name.
    remote_path: the remote file path in |bucket|.
    local_path: path of the local file to be uploaded.
    publicly_readable: whether the uploaded file has publicly readable
    permission.

  Returns:
    The url where the file is uploaded to.
  """
  url = 'gs://%s/%s' % (bucket, remote_path)
  command_and_args = ['cp']
  extra_info = ''
  if publicly_readable:
    command_and_args += ['-a', 'public-read']
    extra_info = ' (publicly readable)'
  command_and_args += [local_path, url]
  logging.info('Uploading %s to %s%s' % (local_path, url, extra_info))
  _RunCommand(command_and_args)
  return 'https://console.developers.google.com/m/cloudstorage/b/%s/o/%s' % (
      bucket, remote_path)


def GetIfHashChanged(cs_path, download_path, bucket, file_hash):
  """Downloads |download_path| to |file_path| if |file_path| doesn't exist or
     it's hash doesn't match |file_hash|.

  Returns:
    True if the binary was changed.
  Raises:
    CredentialsError if the user has no configured credentials.
    PermissionError if the user does not have permission to access the bucket.
    NotFoundError if the file is not in the given bucket in cloud_storage.
  """
  if (os.path.exists(download_path) and
      CalculateHash(download_path) == file_hash):
    return False
  Get(bucket, cs_path, download_path)
  return True


def GetIfChanged(file_path, bucket):
  """Gets the file at file_path if it has a hash file that doesn't match or
  if there is no local copy of file_path, but there is a hash file for it.

  Returns:
    True if the binary was changed.
  Raises:
    CredentialsError if the user has no configured credentials.
    PermissionError if the user does not have permission to access the bucket.
    NotFoundError if the file is not in the given bucket in cloud_storage.
  """
  hash_path = file_path + '.sha1'
  if not os.path.exists(hash_path):
    logging.warning('Hash file not found: %s' % hash_path)
    return False

  expected_hash = ReadHash(hash_path)
  if os.path.exists(file_path) and CalculateHash(file_path) == expected_hash:
    return False

  Get(bucket, expected_hash, file_path)
  return True

# TODO(aiolos): remove @decorators.Cache for http://crbug.com/459787
@decorators.Cache
def GetFilesInDirectoryIfChanged(directory, bucket):
  """ Scan the directory for .sha1 files, and download them from the given
  bucket in cloud storage if the local and remote hash don't match or
  there is no local copy.
  """
  if not os.path.isdir(directory):
    raise ValueError('Must provide a valid directory.')
  # Don't allow the root directory to be a serving_dir.
  if directory == os.path.abspath(os.sep):
    raise ValueError('Trying to serve root directory from HTTP server.')
  for dirpath, _, filenames in os.walk(directory):
    for filename in filenames:
      path_name, extension = os.path.splitext(
          os.path.join(dirpath, filename))
      if extension != '.sha1':
        continue
      GetIfChanged(path_name, bucket)

def CalculateHash(file_path):
  """Calculates and returns the hash of the file at file_path."""
  sha1 = hashlib.sha1()
  with open(file_path, 'rb') as f:
    while True:
      # Read in 1mb chunks, so it doesn't all have to be loaded into memory.
      chunk = f.read(1024*1024)
      if not chunk:
        break
      sha1.update(chunk)
  return sha1.hexdigest()


def ReadHash(hash_path):
  with open(hash_path, 'rb') as f:
    return f.read(1024).rstrip()
