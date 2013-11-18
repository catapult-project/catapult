# Copyright (c) 2013 The Chromium Authors. All rights reserved.
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

from telemetry.core import util


PUBLIC_BUCKET = 'chromium-telemetry'
INTERNAL_BUCKET = 'chrome-telemetry'


_GSUTIL_URL = 'http://storage.googleapis.com/pub/gsutil.tar.gz'
_DOWNLOAD_PATH = os.path.join(util.GetTelemetryDir(), 'third_party', 'gsutil')


class CloudStorageError(Exception):
  @staticmethod
  def _GetConfigInstructions(gsutil_path):
    return ('To configure your credentials:\n'
            '  1. Run "%s config" and follow its instructions.\n'
            '  2. If you have a @google.com account, use that one.\n'
            '  3. Leave the project-id field blank.' % gsutil_path)


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


def _DownloadGsutil():
  logging.info('Downloading gsutil')
  response = urllib2.urlopen(_GSUTIL_URL)
  with tarfile.open(fileobj=cStringIO.StringIO(response.read())) as tar_file:
    tar_file.extractall(os.path.dirname(_DOWNLOAD_PATH))
  logging.info('Downloaded gsutil to %s' % _DOWNLOAD_PATH)

  return os.path.join(_DOWNLOAD_PATH, 'gsutil')


def _FindGsutil():
  """Return the gsutil executable path. If we can't find it, download it."""
  search_paths = [_DOWNLOAD_PATH] + os.environ['PATH'].split(os.pathsep)

  # Look for a depot_tools installation.
  for path in search_paths:
    gsutil_path = os.path.join(path, 'third_party', 'gsutil', 'gsutil')
    if os.path.isfile(gsutil_path):
      return gsutil_path

  # Look for a gsutil installation.
  for path in search_paths:
    gsutil_path = os.path.join(path, 'gsutil')
    if os.path.isfile(gsutil_path):
      return gsutil_path

  # Failed to find it. Download it!
  return _DownloadGsutil()


def _RunCommand(args):
  gsutil_path = _FindGsutil()
  gsutil = subprocess.Popen([sys.executable, gsutil_path] + args,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, stderr = gsutil.communicate()

  if gsutil.returncode:
    if stderr.startswith('You are attempting to access protected data with '
        'no configured credentials.'):
      raise CredentialsError(gsutil_path)
    if 'status=403' in stderr:
      raise PermissionError(gsutil_path)
    if stderr.startswith('InvalidUriError') or 'No such object' in stderr:
      raise NotFoundError(stderr)
    raise CloudStorageError(stderr)

  return stdout


def List(bucket):
  stdout = _RunCommand(['ls', 'gs://%s' % bucket])
  return [url.split('/')[-1] for url in stdout.splitlines()]


def Delete(bucket, remote_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Deleting %s' % url)
  _RunCommand(['rm', url])


def Get(bucket, remote_path, local_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Downloading %s to %s' % (url, local_path))
  _RunCommand(['cp', url, local_path])


def Insert(bucket, remote_path, local_path):
  url = 'gs://%s/%s' % (bucket, remote_path)
  logging.info('Uploading %s to %s' % (local_path, url))
  _RunCommand(['cp', local_path, url])


def GetIfChanged(bucket, file_path):
  """Gets the file at file_path if it has a hash file that doesn't match.

  If the file is not in Cloud Storage, log a warning instead of raising an
  exception. We assume that the user just hasn't uploaded the file yet.

  Returns:
    True if the binary was changed.
  """
  hash_path = file_path + '.sha1'
  if not os.path.exists(hash_path):
    return False

  with open(hash_path, 'rb') as f:
    expected_hash = f.read(1024).rstrip()
  if os.path.exists(file_path) and GetHash(file_path) == expected_hash:
    return False

  try:
    Get(bucket, expected_hash, file_path)
  except NotFoundError:
    logging.warning('Unable to update file %s from Cloud Storage.' % file_path)
  return True


def GetHash(file_path):
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
