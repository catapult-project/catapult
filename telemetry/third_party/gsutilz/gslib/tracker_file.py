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
"""Helper functions for tracker file functionality."""

import errno
import hashlib
import os
import re

from boto import config
from gslib.exception import CommandException
from gslib.util import CreateDirIfNeeded
from gslib.util import GetGsutilStateDir
from gslib.util import ResumableThreshold
from gslib.util import UTF8

# The maximum length of a file name can vary wildly between different
# operating systems, so we always ensure that tracker files are less
# than 100 characters in order to avoid any such issues.
MAX_TRACKER_FILE_NAME_LENGTH = 100


TRACKER_FILE_UNWRITABLE_EXCEPTION_TEXT = (
    'Couldn\'t write tracker file (%s): %s. This can happen if gsutil is '
    'configured to save tracker files to an unwritable directory)')


class TrackerFileType(object):
  UPLOAD = 'upload'
  DOWNLOAD = 'download'
  PARALLEL_UPLOAD = 'parallel_upload'
  REWRITE = 'rewrite'


def _HashFilename(filename):
  """Apply a hash function (SHA1) to shorten the passed file name.

  The spec for the hashed file name is as follows:

      TRACKER_<hash>_<trailing>

  where hash is a SHA1 hash on the original file name and trailing is
  the last 16 chars from the original file name. Max file name lengths
  vary by operating system so the goal of this function is to ensure
  the hashed version takes fewer than 100 characters.

  Args:
    filename: file name to be hashed.

  Returns:
    shorter, hashed version of passed file name
  """
  if isinstance(filename, unicode):
    filename = filename.encode(UTF8)
  else:
    filename = unicode(filename, UTF8).encode(UTF8)
  m = hashlib.sha1(filename)
  return 'TRACKER_' + m.hexdigest() + '.' + filename[-16:]


def CreateTrackerDirIfNeeded():
  """Looks up or creates the gsutil tracker file directory.

  This is the configured directory where gsutil keeps its resumable transfer
  tracker files. This function creates it if it doesn't already exist.

  Returns:
    The pathname to the tracker directory.
  """
  tracker_dir = config.get(
      'GSUtil', 'resumable_tracker_dir',
      os.path.join(GetGsutilStateDir(), 'tracker-files'))
  CreateDirIfNeeded(tracker_dir)
  return tracker_dir


def GetRewriteTrackerFilePath(src_bucket_name, src_obj_name, dst_bucket_name,
                              dst_obj_name, api_selector):
  """Gets the tracker file name described by the arguments.

  Args:
    src_bucket_name: Source bucket (string).
    src_obj_name: Source object (string).
    dst_bucket_name: Destination bucket (string).
    dst_obj_name: Destination object (string)
    api_selector: API to use for this operation.

  Returns:
    File path to tracker file.
  """
  # Encode the src and dest bucket and object names into the tracker file
  # name.
  res_tracker_file_name = (
      re.sub('[/\\\\]', '_', 'rewrite__%s__%s__%s__%s__%s.token' %
             (src_bucket_name, src_obj_name, dst_bucket_name,
              dst_obj_name, api_selector)))

  return _HashAndReturnPath(res_tracker_file_name, TrackerFileType.REWRITE)


def GetTrackerFilePath(dst_url, tracker_file_type, api_selector, src_url=None):
  """Gets the tracker file name described by the arguments.

  Args:
    dst_url: Destination URL for tracker file.
    tracker_file_type: TrackerFileType for this operation.
    api_selector: API to use for this operation.
    src_url: Source URL for the source file name for parallel uploads.

  Returns:
    File path to tracker file.
  """
  if tracker_file_type == TrackerFileType.UPLOAD:
    # Encode the dest bucket and object name into the tracker file name.
    res_tracker_file_name = (
        re.sub('[/\\\\]', '_', 'resumable_upload__%s__%s__%s.url' %
               (dst_url.bucket_name, dst_url.object_name, api_selector)))
  elif tracker_file_type == TrackerFileType.DOWNLOAD:
    # Encode the fully-qualified dest file name into the tracker file name.
    res_tracker_file_name = (
        re.sub('[/\\\\]', '_', 'resumable_download__%s__%s.etag' %
               (os.path.realpath(dst_url.object_name), api_selector)))
  elif tracker_file_type == TrackerFileType.PARALLEL_UPLOAD:
    # Encode the dest bucket and object names as well as the source file name
    # into the tracker file name.
    res_tracker_file_name = (
        re.sub('[/\\\\]', '_', 'parallel_upload__%s__%s__%s__%s.url' %
               (dst_url.bucket_name, dst_url.object_name,
                src_url, api_selector)))
  elif tracker_file_type == TrackerFileType.REWRITE:
    # Should use GetRewriteTrackerFilePath instead.
    raise NotImplementedError()

  return _HashAndReturnPath(res_tracker_file_name, tracker_file_type)


def _HashAndReturnPath(res_tracker_file_name, tracker_file_type):
  resumable_tracker_dir = CreateTrackerDirIfNeeded()
  hashed_tracker_file_name = _HashFilename(res_tracker_file_name)
  tracker_file_name = '%s_%s' % (str(tracker_file_type).lower(),
                                 hashed_tracker_file_name)
  tracker_file_path = '%s%s%s' % (resumable_tracker_dir, os.sep,
                                  tracker_file_name)
  assert len(tracker_file_name) < MAX_TRACKER_FILE_NAME_LENGTH
  return tracker_file_path


def DeleteTrackerFile(tracker_file_name):
  if tracker_file_name and os.path.exists(tracker_file_name):
    os.unlink(tracker_file_name)


def HashRewriteParameters(
    src_obj_metadata, dst_obj_metadata, projection, src_generation=None,
    gen_match=None, meta_gen_match=None, canned_acl=None, fields=None,
    max_bytes_per_call=None):
  """Creates an MD5 hex digest of the parameters for a rewrite call.

  Resuming rewrites requires that the input parameters are identical. Thus,
  the rewrite tracker file needs to represent the input parameters. For
  easy comparison, hash the input values. If a user does a performs a
  same-source/same-destination rewrite via a different command (for example,
  with a changed ACL), the hashes will not match and we will restart the
  rewrite from the beginning.

  Args:
    src_obj_metadata: apitools Object describing source object. Must include
      bucket, name, and etag.
    dst_obj_metadata: apitools Object describing destination object. Must
      include bucket and object name
    projection: Projection used for the API call.
    src_generation: Optional source generation.
    gen_match: Optional generation precondition.
    meta_gen_match: Optional metageneration precondition.
    canned_acl: Optional canned ACL string.
    fields: Optional fields to include in response.
    max_bytes_per_call: Optional maximum bytes rewritten per call.

  Returns:
    MD5 hex digest Hash of the input parameters, or None if required parameters
    are missing.
  """
  if (not src_obj_metadata or
      not src_obj_metadata.bucket or
      not src_obj_metadata.name or
      not src_obj_metadata.etag or
      not dst_obj_metadata or
      not dst_obj_metadata.bucket or
      not dst_obj_metadata.name or
      not projection):
    return
  md5_hash = hashlib.md5()
  for input_param in (
      src_obj_metadata, dst_obj_metadata, projection, src_generation,
      gen_match, meta_gen_match, canned_acl, fields, max_bytes_per_call):
    md5_hash.update(str(input_param))
  return md5_hash.hexdigest()


def ReadRewriteTrackerFile(tracker_file_name, rewrite_params_hash):
  """Attempts to read a rewrite tracker file.

  Args:
    tracker_file_name: Tracker file path string.
    rewrite_params_hash: MD5 hex digest of rewrite call parameters constructed
        by HashRewriteParameters.

  Returns:
    String rewrite_token for resuming rewrite requests if a matching tracker
    file exists, None otherwise (which will result in starting a new rewrite).
  """
  # Check to see if we already have a matching tracker file.
  tracker_file = None
  if not rewrite_params_hash:
    return
  try:
    tracker_file = open(tracker_file_name, 'r')
    existing_hash = tracker_file.readline().rstrip('\n')
    if existing_hash == rewrite_params_hash:
      # Next line is the rewrite token.
      return tracker_file.readline().rstrip('\n')
  except IOError as e:
    # Ignore non-existent file (happens first time a rewrite is attempted.
    if e.errno != errno.ENOENT:
      print('Couldn\'t read Copy tracker file (%s): %s. Restarting copy '
            'from scratch.' %
            (tracker_file_name, e.strerror))
  finally:
    if tracker_file:
      tracker_file.close()


def WriteRewriteTrackerFile(tracker_file_name, rewrite_params_hash,
                            rewrite_token):
  """Writes a rewrite tracker file.

  Args:
    tracker_file_name: Tracker file path string.
    rewrite_params_hash: MD5 hex digest of rewrite call parameters constructed
        by HashRewriteParameters.
    rewrite_token: Rewrite token string returned by the service.
  """
  _WriteTrackerFile(tracker_file_name, '%s\n%s\n' % (rewrite_params_hash,
                                                     rewrite_token))


def ReadOrCreateDownloadTrackerFile(src_obj_metadata, dst_url,
                                    api_selector):
  """Checks for a download tracker file and creates one if it does not exist.

  Args:
    src_obj_metadata: Metadata for the source object. Must include
                      etag and size.
    dst_url: Destination file StorageUrl.
    api_selector: API mode to use (for tracker file naming).

  Returns:
    True if the tracker file already exists (resume existing download),
    False if we created a new tracker file (new download).
  """
  if src_obj_metadata.size < ResumableThreshold():
    # Don't create a tracker file for a small downloads; cross-process resumes
    # won't work, but restarting a small download is inexpensive.
    return False

  assert src_obj_metadata.etag
  tracker_file_name = GetTrackerFilePath(
      dst_url, TrackerFileType.DOWNLOAD, api_selector)
  tracker_file = None

  # Check to see if we already have a matching tracker file.
  try:
    tracker_file = open(tracker_file_name, 'r')
    etag_value = tracker_file.readline().rstrip('\n')
    if etag_value == src_obj_metadata.etag:
      return True
  except IOError as e:
    # Ignore non-existent file (happens first time a download
    # is attempted on an object), but warn user for other errors.
    if e.errno != errno.ENOENT:
      print('Couldn\'t read URL tracker file (%s): %s. Restarting '
            'download from scratch.' %
            (tracker_file_name, e.strerror))
  finally:
    if tracker_file:
      tracker_file.close()

  # Otherwise, create a new tracker file and start from scratch.
  _WriteTrackerFile(tracker_file_name, '%s\n' % src_obj_metadata.etag)


def _WriteTrackerFile(tracker_file_name, data):
  """Creates a tracker file, storing the input data."""
  try:
    with os.fdopen(os.open(tracker_file_name,
                           os.O_WRONLY | os.O_CREAT, 0600), 'w') as tf:
      tf.write(data)
    return False
  except (IOError, OSError) as e:
    raise RaiseUnwritableTrackerFileException(tracker_file_name, e.strerror)


def RaiseUnwritableTrackerFileException(tracker_file_name, error_str):
  """Raises an exception when unable to write the tracker file."""
  raise CommandException(TRACKER_FILE_UNWRITABLE_EXCEPTION_TEXT %
                         (tracker_file_name, error_str))
