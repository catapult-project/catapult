# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrappers for gsutil, for basic interaction with Google Cloud Storage."""

import cStringIO
import hashlib
import logging
import os
import subprocess
import sys
import tarfile
import urllib2

from telemetry.core.backends.chrome import cros_interface
from telemetry.core import util


PUBLIC_BUCKET = 'chromium-telemetry'
PARTNER_BUCKET = 'chrome-partner-telemetry'
INTERNAL_BUCKET = 'chrome-telemetry'


_GSUTIL_URL = 'http://storage.googleapis.com/pub/gsutil.tar.gz'
_DOWNLOAD_PATH = os.path.join(util.GetTelemetryDir(), 'third_party', 'gsutil')
# TODO(tbarzic): A workaround for http://crbug.com/386416 and
#     http://crbug.com/359293. See |_RunCommand|.
_CROS_GSUTIL_HOME_WAR = '/home/chromeos-test/'

class CloudStorageError(Exception):
  @staticmethod
  def _GetConfigInstructions(gsutil_path):
    if SupportsProdaccess(gsutil_path) and _FindExecutableInPath('prodaccess'):
      return 'Run prodaccess to authenticate.'
    else:
      if cros_interface.IsRunningOnCrosDevice():
        gsutil_path = ('HOME=%s %s' % (_CROS_GSUTIL_HOME_WAR, gsutil_path))
      return ('To configure your credentials:\n'
              '  1. Run "%s config" and follow its instructions.\n'
              '  2. If you have a @google.com account, use that account.\n'
              '  3. For the project-id, just enter 0.' % gsutil_path)


class PermissionError(CloudStorageError):
  def __init__(self, gsutil_path):
    super(PermissionError, self).__init__(
        'Attempted to access a file from Cloud Storage but you don\'t '
        'have permission. ' + self._GetConfigInstructions(gsutil_path))


class CredentialsError(CloudStorageError):
  def __init__(self, gsutil_path):
    super(CredentialsError, self).__init__(
        'Attempted to access a file from Cloud Storage but you have no '
        'configured credentials. ' + self._GetConfigInstructions(gsutil_path))


class NotFoundError(CloudStorageError):
  pass


# TODO(tonyg/dtu): Can this be replaced with distutils.spawn.find_executable()?
def _FindExecutableInPath(relative_executable_path, *extra_search_paths):
  for path in list(extra_search_paths) + os.environ['PATH'].split(os.pathsep):
    executable_path = os.path.join(path, relative_executable_path)
    if os.path.isfile(executable_path) and os.access(executable_path, os.X_OK):
      return executable_path
  return None


def _DownloadGsutil():
  logging.info('Downloading gsutil')
  response = urllib2.urlopen(_GSUTIL_URL)
  with tarfile.open(fileobj=cStringIO.StringIO(response.read())) as tar_file:
    tar_file.extractall(os.path.dirname(_DOWNLOAD_PATH))
  logging.info('Downloaded gsutil to %s' % _DOWNLOAD_PATH)

  return os.path.join(_DOWNLOAD_PATH, 'gsutil')


def FindGsutil():
  """Return the gsutil executable path. If we can't find it, download it."""
  # Look for a depot_tools installation.
  gsutil_path = _FindExecutableInPath(
      os.path.join('third_party', 'gsutil', 'gsutil'), _DOWNLOAD_PATH)
  if gsutil_path:
    return gsutil_path

  # Look for a gsutil installation.
  gsutil_path = _FindExecutableInPath('gsutil', _DOWNLOAD_PATH)
  if gsutil_path:
    return gsutil_path

  # Failed to find it. Download it!
  return _DownloadGsutil()


def SupportsProdaccess(gsutil_path):
  with open(gsutil_path, 'r') as gsutil:
    return 'prodaccess' in gsutil.read()


def _RunCommand(args):
  gsutil_path = FindGsutil()

  # On cros device, as telemetry is running as root, home will be set to /root/,
  # which is not writable. gsutil will attempt to create a download tracker dir
  # in home dir and fail. To avoid this, override HOME dir to something writable
  # when running on cros device.
  #
  # TODO(tbarzic): Figure out a better way to handle gsutil on cros.
  #     http://crbug.com/386416, http://crbug.com/359293.
  gsutil_env = None
  if cros_interface.IsRunningOnCrosDevice():
    gsutil_env = os.environ.copy()
    gsutil_env['HOME'] = _CROS_GSUTIL_HOME_WAR

  gsutil = subprocess.Popen([sys.executable, gsutil_path] + args,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=gsutil_env)
  stdout, stderr = gsutil.communicate()

  if gsutil.returncode:
    if stderr.startswith((
        'You are attempting to access protected data with no configured',
        'Failure: No handler was ready to authenticate.')):
      raise CredentialsError(gsutil_path)
    if 'status=403' in stderr or 'status 403' in stderr:
      raise PermissionError(gsutil_path)
    if (stderr.startswith('InvalidUriError') or 'No such object' in stderr or
        'No URLs matched' in stderr):
      raise NotFoundError(stderr)
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


def Delete(bucket, remote_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Deleting %s' % url)
  _RunCommand(['rm', url])


def Get(bucket, remote_path, local_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Downloading %s to %s' % (url, local_path))
  _RunCommand(['cp', url, local_path])


def Insert(bucket, remote_path, local_path, publicly_readable=False):
  url = 'gs://%s/%s' % (bucket, remote_path)
  command_and_args = ['cp']
  extra_info = ''
  if publicly_readable:
    command_and_args += ['-a', 'public-read']
    extra_info = ' (publicly readable)'
  command_and_args += [local_path, url]
  logging.info('Uploading %s to %s%s' % (local_path, url, extra_info))
  _RunCommand(command_and_args)


def GetIfChanged(file_path, bucket=None):
  """Gets the file at file_path if it has a hash file that doesn't match.

  If the file is not in Cloud Storage, log a warning instead of raising an
  exception. We assume that the user just hasn't uploaded the file yet.

  Returns:
    True if the binary was changed.
  """
  hash_path = file_path + '.sha1'
  if not os.path.exists(hash_path):
    logging.warning('Hash file not found: %s' % hash_path)
    return False

  expected_hash = ReadHash(hash_path)
  if os.path.exists(file_path) and CalculateHash(file_path) == expected_hash:
    return False

  if bucket:
    buckets = [bucket]
  else:
    buckets = [PUBLIC_BUCKET, PARTNER_BUCKET, INTERNAL_BUCKET]

  for bucket in buckets:
    try:
      url = 'gs://%s/%s' % (bucket, expected_hash)
      _RunCommand(['cp', url, file_path])
      logging.info('Downloaded %s to %s' % (url, file_path))
      return True
    except NotFoundError:
      continue

  logging.warning('Unable to find file in Cloud Storage: %s', file_path)
  return False


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
