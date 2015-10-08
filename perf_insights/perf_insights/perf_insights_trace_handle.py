# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import subprocess
import sys

from perf_insights import trace_handle


_GSUTIL_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'third_party', 'gsutil', 'gsutil'))


class CloudStorageError(Exception):
  @staticmethod
  def _GetConfigInstructions():
    command = _GSUTIL_PATH
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


class PerfInsightsTraceHandle(trace_handle.TraceHandle):
  def __init__(self, run_info, cache_directory):
    super(PerfInsightsTraceHandle, self).__init__(run_info)
    file_name = run_info.run_id.split('/')[-1]
    self.cache_file = os.path.join(
        cache_directory, file_name + '.gz')

  def _DownloadFile(self):
    # TODO(simonhatch): Once catapult_base is migrated to catapult, let's
    # use cloud_storage.py instead of duplicating a lot of the code here.
    args = [sys.executable, _GSUTIL_PATH, 'cp', self.run_info.url,
            self.cache_file]
    gsutil = subprocess.Popen(args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
    _, stderr = gsutil.communicate()

    if gsutil.returncode:
      if stderr.startswith((
          'You are attempting to access protected data with no configured',
          'Failure: No handler was ready to authenticate.')):
        raise CredentialsError()
      if ('status=403' in stderr or 'status 403' in stderr or
          '403 Forbidden' in stderr):
        raise PermissionError()
      if (stderr.startswith('InvalidUriError') or 'No such object' in stderr or
          'No URLs matched' in stderr or
          'One or more URLs matched no' in stderr):
        raise NotFoundError(stderr)
      if '500 Internal Server Error' in stderr:
        raise ServerError(stderr)
      raise CloudStorageError(stderr)
    return gsutil.returncode

  def Open(self):
    if not os.path.exists(self.cache_file):
      if self._DownloadFile():
        return None
    return open(self.cache_file, 'r')
