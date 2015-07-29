# -*- coding: utf-8 -*-
# Copyright 2011 Google Inc. All Rights Reserved.
# Copyright 2011, Nexenta Systems Inc.
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
"""Helper functions for copy functionality."""

from __future__ import absolute_import

import base64
from collections import namedtuple
import csv
import datetime
import errno
import gzip
from hashlib import md5
import json
import logging
import mimetypes
import multiprocessing
import os
import pickle
import random
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import time
import traceback

from boto import config
import crcmod

import gslib
from gslib.cloud_api import ArgumentException
from gslib.cloud_api import CloudApi
from gslib.cloud_api import NotFoundException
from gslib.cloud_api import PreconditionException
from gslib.cloud_api import Preconditions
from gslib.cloud_api import ResumableDownloadException
from gslib.cloud_api import ResumableUploadAbortException
from gslib.cloud_api import ResumableUploadException
from gslib.cloud_api import ResumableUploadStartOverException
from gslib.cloud_api_helper import GetDownloadSerializationDict
from gslib.commands.compose import MAX_COMPOSE_ARITY
from gslib.commands.config import DEFAULT_PARALLEL_COMPOSITE_UPLOAD_COMPONENT_SIZE
from gslib.commands.config import DEFAULT_PARALLEL_COMPOSITE_UPLOAD_THRESHOLD
from gslib.cs_api_map import ApiSelector
from gslib.daisy_chain_wrapper import DaisyChainWrapper
from gslib.exception import CommandException
from gslib.exception import HashMismatchException
from gslib.file_part import FilePart
from gslib.hashing_helper import Base64EncodeHash
from gslib.hashing_helper import CalculateB64EncodedMd5FromContents
from gslib.hashing_helper import CalculateHashesFromContents
from gslib.hashing_helper import GetDownloadHashAlgs
from gslib.hashing_helper import GetUploadHashAlgs
from gslib.hashing_helper import HashingFileUploadWrapper
from gslib.parallelism_framework_util import ThreadAndProcessSafeDict
from gslib.parallelism_framework_util import ThreadSafeDict
from gslib.progress_callback import ConstructAnnounceText
from gslib.progress_callback import FileProgressCallbackHandler
from gslib.progress_callback import ProgressCallbackWithBackoff
from gslib.resumable_streaming_upload import ResumableStreamingJsonUploadWrapper
from gslib.storage_url import ContainsWildcard
from gslib.storage_url import StorageUrlFromString
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.tracker_file import DeleteTrackerFile
from gslib.tracker_file import GetTrackerFilePath
from gslib.tracker_file import RaiseUnwritableTrackerFileException
from gslib.tracker_file import ReadOrCreateDownloadTrackerFile
from gslib.tracker_file import TrackerFileType
from gslib.translation_helper import AddS3MarkerAclToObjectMetadata
from gslib.translation_helper import CopyObjectMetadata
from gslib.translation_helper import DEFAULT_CONTENT_TYPE
from gslib.translation_helper import GenerationFromUrlAndString
from gslib.translation_helper import ObjectMetadataFromHeaders
from gslib.translation_helper import PreconditionsFromHeaders
from gslib.translation_helper import S3MarkerAclFromObjectMetadata
from gslib.util import CreateLock
from gslib.util import DEFAULT_FILE_BUFFER_SIZE
from gslib.util import GetCloudApiInstance
from gslib.util import GetFileSize
from gslib.util import GetJsonResumableChunkSize
from gslib.util import GetMaxRetryDelay
from gslib.util import GetNumRetries
from gslib.util import GetStreamFromFileUrl
from gslib.util import HumanReadableToBytes
from gslib.util import IS_WINDOWS
from gslib.util import IsCloudSubdirPlaceholder
from gslib.util import MakeHumanReadable
from gslib.util import MIN_SIZE_COMPUTE_LOGGING
from gslib.util import MultiprocessingIsAvailable
from gslib.util import ResumableThreshold
from gslib.util import TEN_MIB
from gslib.util import UTF8
from gslib.wildcard_iterator import CreateWildcardIterator

# pylint: disable=g-import-not-at-top
if IS_WINDOWS:
  import msvcrt
  from ctypes import c_int
  from ctypes import c_uint64
  from ctypes import c_char_p
  from ctypes import c_wchar_p
  from ctypes import windll
  from ctypes import POINTER
  from ctypes import WINFUNCTYPE
  from ctypes import WinError

# Declare copy_helper_opts as a global because namedtuple isn't aware of
# assigning to a class member (which breaks pickling done by multiprocessing).
# For details see
# http://stackoverflow.com/questions/16377215/how-to-pickle-a-namedtuple-instance-correctly
# Similarly can't pickle logger.
# pylint: disable=global-at-module-level
global global_copy_helper_opts, global_logger

# In-memory map of local files that are currently opened for write. Used to
# ensure that if we write to the same file twice (say, for example, because the
# user specified two identical source URLs), the writes occur serially.
global open_files_map
open_files_map = (
    ThreadSafeDict() if (IS_WINDOWS or not MultiprocessingIsAvailable()[0])
    else ThreadAndProcessSafeDict(multiprocessing.Manager()))

# For debugging purposes; if True, files and objects that fail hash validation
# will be saved with the below suffix appended.
_RENAME_ON_HASH_MISMATCH = False
_RENAME_ON_HASH_MISMATCH_SUFFIX = '_corrupt'

PARALLEL_UPLOAD_TEMP_NAMESPACE = (
    u'/gsutil/tmp/parallel_composite_uploads/for_details_see/gsutil_help_cp/')

PARALLEL_UPLOAD_STATIC_SALT = u"""
PARALLEL_UPLOAD_SALT_TO_PREVENT_COLLISIONS.
The theory is that no user will have prepended this to the front of
one of their object names and then done an MD5 hash of the name, and
then prepended PARALLEL_UPLOAD_TEMP_NAMESPACE to the front of their object
name. Note that there will be no problems with object name length since we
hash the original name.
"""

# When uploading a file, get the following fields in the response for
# filling in command output and manifests.
UPLOAD_RETURN_FIELDS = ['crc32c', 'etag', 'generation', 'md5Hash', 'size']

# This tuple is used only to encapsulate the arguments needed for
# command.Apply() in the parallel composite upload case.
# Note that content_type is used instead of a full apitools Object() because
# apitools objects are not picklable.
# filename: String name of file.
# file_start: start byte of file (may be in the middle of a file for partitioned
#             files).
# file_length: length of upload (may not be the entire length of a file for
#              partitioned files).
# src_url: FileUrl describing the source file.
# dst_url: CloudUrl describing the destination component file.
# canned_acl: canned_acl to apply to the uploaded file/component.
# content_type: content-type for final object, used for setting content-type
#               of components and final object.
# tracker_file: tracker file for this component.
# tracker_file_lock: tracker file lock for tracker file(s).
PerformParallelUploadFileToObjectArgs = namedtuple(
    'PerformParallelUploadFileToObjectArgs',
    'filename file_start file_length src_url dst_url canned_acl '
    'content_type tracker_file tracker_file_lock')

ObjectFromTracker = namedtuple('ObjectFromTracker',
                               'object_name generation')

# TODO: Refactor this file to be less cumbersome. In particular, some of the
# different paths (e.g., uploading a file to an object vs. downloading an
# object to a file) could be split into separate files.

# Chunk size to use while zipping/unzipping gzip files.
GZIP_CHUNK_SIZE = 8192

PARALLEL_COMPOSITE_SUGGESTION_THRESHOLD = 150 * 1024 * 1024

# S3 requires special Multipart upload logic (that we currently don't implement)
# for files > 5GiB in size.
S3_MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024

suggested_parallel_composites = False


class FileConcurrencySkipError(Exception):
  """Raised when skipping a file due to a concurrent, duplicate copy."""


def _RmExceptionHandler(cls, e):
  """Simple exception handler to allow post-completion status."""
  cls.logger.error(str(e))


def _ParallelUploadCopyExceptionHandler(cls, e):
  """Simple exception handler to allow post-completion status."""
  cls.logger.error(str(e))
  cls.op_failure_count += 1
  cls.logger.debug('\n\nEncountered exception while copying:\n%s\n',
                   traceback.format_exc())


def _PerformParallelUploadFileToObject(cls, args, thread_state=None):
  """Function argument to Apply for performing parallel composite uploads.

  Args:
    cls: Calling Command class.
    args: PerformParallelUploadFileToObjectArgs tuple describing the target.
    thread_state: gsutil Cloud API instance to use for the operation.

  Returns:
    StorageUrl representing a successfully uploaded component.
  """
  fp = FilePart(args.filename, args.file_start, args.file_length)
  gsutil_api = GetCloudApiInstance(cls, thread_state=thread_state)
  with fp:
    # We take many precautions with the component names that make collisions
    # effectively impossible. Specifying preconditions will just allow us to
    # reach a state in which uploads will always fail on retries.
    preconditions = None

    # Fill in content type if one was provided.
    dst_object_metadata = apitools_messages.Object(
        name=args.dst_url.object_name,
        bucket=args.dst_url.bucket_name,
        contentType=args.content_type)

    try:
      if global_copy_helper_opts.canned_acl:
        # No canned ACL support in JSON, force XML API to be used for
        # upload/copy operations.
        orig_prefer_api = gsutil_api.prefer_api
        gsutil_api.prefer_api = ApiSelector.XML
      ret = _UploadFileToObject(args.src_url, fp, args.file_length,
                                args.dst_url, dst_object_metadata,
                                preconditions, gsutil_api, cls.logger, cls,
                                _ParallelUploadCopyExceptionHandler,
                                gzip_exts=None, allow_splitting=False)
    finally:
      if global_copy_helper_opts.canned_acl:
        gsutil_api.prefer_api = orig_prefer_api

  component = ret[2]
  _AppendComponentTrackerToParallelUploadTrackerFile(
      args.tracker_file, component, args.tracker_file_lock)
  return ret


CopyHelperOpts = namedtuple('CopyHelperOpts', [
    'perform_mv',
    'no_clobber',
    'daisy_chain',
    'read_args_from_stdin',
    'print_ver',
    'use_manifest',
    'preserve_acl',
    'canned_acl',
    'skip_unsupported_objects',
    'test_callback_file'])


# pylint: disable=global-variable-undefined
def CreateCopyHelperOpts(perform_mv=False, no_clobber=False, daisy_chain=False,
                         read_args_from_stdin=False, print_ver=False,
                         use_manifest=False, preserve_acl=False,
                         canned_acl=None, skip_unsupported_objects=False,
                         test_callback_file=None):
  """Creates CopyHelperOpts for passing options to CopyHelper."""
  # We create a tuple with union of options needed by CopyHelper and any
  # copy-related functionality in CpCommand, RsyncCommand, or Command class.
  global global_copy_helper_opts
  global_copy_helper_opts = CopyHelperOpts(
      perform_mv=perform_mv,
      no_clobber=no_clobber,
      daisy_chain=daisy_chain,
      read_args_from_stdin=read_args_from_stdin,
      print_ver=print_ver,
      use_manifest=use_manifest,
      preserve_acl=preserve_acl,
      canned_acl=canned_acl,
      skip_unsupported_objects=skip_unsupported_objects,
      test_callback_file=test_callback_file)
  return global_copy_helper_opts


# pylint: disable=global-variable-undefined
# pylint: disable=global-variable-not-assigned
def GetCopyHelperOpts():
  """Returns namedtuple holding CopyHelper options."""
  global global_copy_helper_opts
  return global_copy_helper_opts


def _SelectDownloadStrategy(dst_url):
  """Get download strategy based on the destination object.

  Args:
    dst_url: Destination StorageUrl.

  Returns:
    gsutil Cloud API DownloadStrategy.
  """
  dst_is_special = False
  if dst_url.IsFileUrl():
    # Check explicitly first because os.stat doesn't work on 'nul' in Windows.
    if dst_url.object_name == os.devnull:
      dst_is_special = True
    try:
      mode = os.stat(dst_url.object_name).st_mode
      if stat.S_ISCHR(mode):
        dst_is_special = True
    except OSError:
      pass

  if dst_is_special:
    return CloudApi.DownloadStrategy.ONE_SHOT
  else:
    return CloudApi.DownloadStrategy.RESUMABLE


def _GetUploadTrackerData(tracker_file_name, logger):
  """Reads tracker data from an upload tracker file if it exists.

  Args:
    tracker_file_name: Tracker file name for this upload.
    logger: for outputting log messages.

  Returns:
    Serialization data if the tracker file already exists (resume existing
    upload), None otherwise.
  """
  tracker_file = None

  # If we already have a matching tracker file, get the serialization data
  # so that we can resume the upload.
  try:
    tracker_file = open(tracker_file_name, 'r')
    tracker_data = tracker_file.read()
    return tracker_data
  except IOError as e:
    # Ignore non-existent file (happens first time a upload is attempted on an
    # object, or when re-starting an upload after a
    # ResumableUploadStartOverException), but warn user for other errors.
    if e.errno != errno.ENOENT:
      logger.warn('Couldn\'t read upload tracker file (%s): %s. Restarting '
                  'upload from scratch.', tracker_file_name, e.strerror)
  finally:
    if tracker_file:
      tracker_file.close()


def InsistDstUrlNamesContainer(exp_dst_url, have_existing_dst_container,
                               command_name):
  """Ensures the destination URL names a container.

  Acceptable containers include directory, bucket, bucket
  subdir, and non-existent bucket subdir.

  Args:
    exp_dst_url: Wildcard-expanded destination StorageUrl.
    have_existing_dst_container: bool indicator of whether exp_dst_url
      names a container (directory, bucket, or existing bucket subdir).
    command_name: Name of command making call. May not be the same as the
        calling class's self.command_name in the case of commands implemented
        atop other commands (like mv command).

  Raises:
    CommandException: if the URL being checked does not name a container.
  """
  if ((exp_dst_url.IsFileUrl() and not exp_dst_url.IsDirectory()) or
      (exp_dst_url.IsCloudUrl() and exp_dst_url.IsBucket()
       and not have_existing_dst_container)):
    raise CommandException('Destination URL must name a directory, bucket, '
                           'or bucket\nsubdirectory for the multiple '
                           'source form of the %s command.' % command_name)


def _ShouldTreatDstUrlAsBucketSubDir(have_multiple_srcs, dst_url,
                                     have_existing_dest_subdir,
                                     src_url_names_container,
                                     recursion_requested):
  """Checks whether dst_url should be treated as a bucket "sub-directory".

  The decision about whether something constitutes a bucket "sub-directory"
  depends on whether there are multiple sources in this request and whether
  there is an existing bucket subdirectory. For example, when running the
  command:
    gsutil cp file gs://bucket/abc
  if there's no existing gs://bucket/abc bucket subdirectory we should copy
  file to the object gs://bucket/abc. In contrast, if
  there's an existing gs://bucket/abc bucket subdirectory we should copy
  file to gs://bucket/abc/file. And regardless of whether gs://bucket/abc
  exists, when running the command:
    gsutil cp file1 file2 gs://bucket/abc
  we should copy file1 to gs://bucket/abc/file1 (and similarly for file2).
  Finally, for recursive copies, if the source is a container then we should
  copy to a container as the target.  For example, when running the command:
    gsutil cp -r dir1 gs://bucket/dir2
  we should copy the subtree of dir1 to gs://bucket/dir2.

  Note that we don't disallow naming a bucket "sub-directory" where there's
  already an object at that URL. For example it's legitimate (albeit
  confusing) to have an object called gs://bucket/dir and
  then run the command
  gsutil cp file1 file2 gs://bucket/dir
  Doing so will end up with objects gs://bucket/dir, gs://bucket/dir/file1,
  and gs://bucket/dir/file2.

  Args:
    have_multiple_srcs: Bool indicator of whether this is a multi-source
        operation.
    dst_url: StorageUrl to check.
    have_existing_dest_subdir: bool indicator whether dest is an existing
      subdirectory.
    src_url_names_container: bool indicator of whether the source URL
      is a container.
    recursion_requested: True if a recursive operation has been requested.

  Returns:
    bool indicator.
  """
  if have_existing_dest_subdir:
    return True
  if dst_url.IsCloudUrl():
    return (have_multiple_srcs or
            (src_url_names_container and recursion_requested))


def _ShouldTreatDstUrlAsSingleton(have_multiple_srcs,
                                  have_existing_dest_subdir, dst_url,
                                  recursion_requested):
  """Checks that dst_url names a single file/object after wildcard expansion.

  It is possible that an object path might name a bucket sub-directory.

  Args:
    have_multiple_srcs: Bool indicator of whether this is a multi-source
        operation.
    have_existing_dest_subdir: bool indicator whether dest is an existing
      subdirectory.
    dst_url: StorageUrl to check.
    recursion_requested: True if a recursive operation has been requested.

  Returns:
    bool indicator.
  """
  if recursion_requested:
    return False
  if dst_url.IsFileUrl():
    return not dst_url.IsDirectory()
  else:  # dst_url.IsCloudUrl()
    return (not have_multiple_srcs and
            not have_existing_dest_subdir and
            dst_url.IsObject())


def ConstructDstUrl(src_url, exp_src_url, src_url_names_container,
                    have_multiple_srcs, exp_dst_url, have_existing_dest_subdir,
                    recursion_requested):
  """Constructs the destination URL for a given exp_src_url/exp_dst_url pair.

  Uses context-dependent naming rules that mimic Linux cp and mv behavior.

  Args:
    src_url: Source StorageUrl to be copied.
    exp_src_url: Single StorageUrl from wildcard expansion of src_url.
    src_url_names_container: True if src_url names a container (including the
        case of a wildcard-named bucket subdir (like gs://bucket/abc,
        where gs://bucket/abc/* matched some objects).
    have_multiple_srcs: True if this is a multi-source request. This can be
        true if src_url wildcard-expanded to multiple URLs or if there were
        multiple source URLs in the request.
    exp_dst_url: the expanded StorageUrl requested for the cp destination.
        Final written path is constructed from this plus a context-dependent
        variant of src_url.
    have_existing_dest_subdir: bool indicator whether dest is an existing
      subdirectory.
    recursion_requested: True if a recursive operation has been requested.

  Returns:
    StorageUrl to use for copy.

  Raises:
    CommandException if destination object name not specified for
    source and source is a stream.
  """
  if _ShouldTreatDstUrlAsSingleton(
      have_multiple_srcs, have_existing_dest_subdir, exp_dst_url,
      recursion_requested):
    # We're copying one file or object to one file or object.
    return exp_dst_url

  if exp_src_url.IsFileUrl() and exp_src_url.IsStream():
    if have_existing_dest_subdir:
      raise CommandException('Destination object name needed when '
                             'source is a stream')
    return exp_dst_url

  if not recursion_requested and not have_multiple_srcs:
    # We're copying one file or object to a subdirectory. Append final comp
    # of exp_src_url to exp_dst_url.
    src_final_comp = exp_src_url.object_name.rpartition(src_url.delim)[-1]
    return StorageUrlFromString('%s%s%s' % (
        exp_dst_url.url_string.rstrip(exp_dst_url.delim),
        exp_dst_url.delim, src_final_comp))

  # Else we're copying multiple sources to a directory, bucket, or a bucket
  # "sub-directory".

  # Ensure exp_dst_url ends in delim char if we're doing a multi-src copy or
  # a copy to a directory. (The check for copying to a directory needs
  # special-case handling so that the command:
  #   gsutil cp gs://bucket/obj dir
  # will turn into file://dir/ instead of file://dir -- the latter would cause
  # the file "dirobj" to be created.)
  # Note: need to check have_multiple_srcs or src_url.names_container()
  # because src_url could be a bucket containing a single object, named
  # as gs://bucket.
  if ((have_multiple_srcs or src_url_names_container or
       (exp_dst_url.IsFileUrl() and exp_dst_url.IsDirectory()))
      and not exp_dst_url.url_string.endswith(exp_dst_url.delim)):
    exp_dst_url = StorageUrlFromString('%s%s' % (exp_dst_url.url_string,
                                                 exp_dst_url.delim))

  # Making naming behavior match how things work with local Linux cp and mv
  # operations depends on many factors, including whether the destination is a
  # container, the plurality of the source(s), and whether the mv command is
  # being used:
  # 1. For the "mv" command that specifies a non-existent destination subdir,
  #    renaming should occur at the level of the src subdir, vs appending that
  #    subdir beneath the dst subdir like is done for copying. For example:
  #      gsutil rm -r gs://bucket
  #      gsutil cp -r dir1 gs://bucket
  #      gsutil cp -r dir2 gs://bucket/subdir1
  #      gsutil mv gs://bucket/subdir1 gs://bucket/subdir2
  #    would (if using cp naming behavior) end up with paths like:
  #      gs://bucket/subdir2/subdir1/dir2/.svn/all-wcprops
  #    whereas mv naming behavior should result in:
  #      gs://bucket/subdir2/dir2/.svn/all-wcprops
  # 2. Copying from directories, buckets, or bucket subdirs should result in
  #    objects/files mirroring the source directory hierarchy. For example:
  #      gsutil cp dir1/dir2 gs://bucket
  #    should create the object gs://bucket/dir2/file2, assuming dir1/dir2
  #    contains file2).
  #    To be consistent with Linux cp behavior, there's one more wrinkle when
  #    working with subdirs: The resulting object names depend on whether the
  #    destination subdirectory exists. For example, if gs://bucket/subdir
  #    exists, the command:
  #      gsutil cp -r dir1/dir2 gs://bucket/subdir
  #    should create objects named like gs://bucket/subdir/dir2/a/b/c. In
  #    contrast, if gs://bucket/subdir does not exist, this same command
  #    should create objects named like gs://bucket/subdir/a/b/c.
  # 3. Copying individual files or objects to dirs, buckets or bucket subdirs
  #    should result in objects/files named by the final source file name
  #    component. Example:
  #      gsutil cp dir1/*.txt gs://bucket
  #    should create the objects gs://bucket/f1.txt and gs://bucket/f2.txt,
  #    assuming dir1 contains f1.txt and f2.txt.

  recursive_move_to_new_subdir = False
  if (global_copy_helper_opts.perform_mv and recursion_requested
      and src_url_names_container and not have_existing_dest_subdir):
    # Case 1. Handle naming rules for bucket subdir mv. Here we want to
    # line up the src_url against its expansion, to find the base to build
    # the new name. For example, running the command:
    #   gsutil mv gs://bucket/abcd gs://bucket/xyz
    # when processing exp_src_url=gs://bucket/abcd/123
    # exp_src_url_tail should become /123
    # Note: mv.py code disallows wildcard specification of source URL.
    recursive_move_to_new_subdir = True
    exp_src_url_tail = (
        exp_src_url.url_string[len(src_url.url_string):])
    dst_key_name = '%s/%s' % (exp_dst_url.object_name.rstrip('/'),
                              exp_src_url_tail.strip('/'))

  elif src_url_names_container and (exp_dst_url.IsCloudUrl() or
                                    exp_dst_url.IsDirectory()):
    # Case 2.  Container copy to a destination other than a file.
    # Build dst_key_name from subpath of exp_src_url past
    # where src_url ends. For example, for src_url=gs://bucket/ and
    # exp_src_url=gs://bucket/src_subdir/obj, dst_key_name should be
    # src_subdir/obj.
    src_url_path_sans_final_dir = GetPathBeforeFinalDir(src_url)
    dst_key_name = exp_src_url.versionless_url_string[
        len(src_url_path_sans_final_dir):].lstrip(src_url.delim)
    # Handle case where dst_url is a non-existent subdir.
    if not have_existing_dest_subdir:
      dst_key_name = dst_key_name.partition(src_url.delim)[-1]
    # Handle special case where src_url was a directory named with '.' or
    # './', so that running a command like:
    #   gsutil cp -r . gs://dest
    # will produce obj names of the form gs://dest/abc instead of
    # gs://dest/./abc.
    if dst_key_name.startswith('.%s' % os.sep):
      dst_key_name = dst_key_name[2:]

  else:
    # Case 3.
    dst_key_name = exp_src_url.object_name.rpartition(src_url.delim)[-1]

  if (not recursive_move_to_new_subdir and (
      exp_dst_url.IsFileUrl() or _ShouldTreatDstUrlAsBucketSubDir(
          have_multiple_srcs, exp_dst_url, have_existing_dest_subdir,
          src_url_names_container, recursion_requested))):
    if exp_dst_url.object_name and exp_dst_url.object_name.endswith(
        exp_dst_url.delim):
      dst_key_name = '%s%s%s' % (
          exp_dst_url.object_name.rstrip(exp_dst_url.delim),
          exp_dst_url.delim, dst_key_name)
    else:
      delim = exp_dst_url.delim if exp_dst_url.object_name else ''
      dst_key_name = '%s%s%s' % (exp_dst_url.object_name or '',
                                 delim, dst_key_name)

  new_exp_dst_url = exp_dst_url.Clone()
  new_exp_dst_url.object_name = dst_key_name.replace(src_url.delim,
                                                     exp_dst_url.delim)
  return new_exp_dst_url


def _CreateDigestsFromDigesters(digesters):
  digests = {}
  if digesters:
    for alg in digesters:
      digests[alg] = base64.encodestring(
          digesters[alg].digest()).rstrip('\n')
  return digests


def _CreateDigestsFromLocalFile(logger, algs, file_name, src_obj_metadata):
  """Creates a base64 CRC32C and/or MD5 digest from file_name.

  Args:
    logger: for outputting log messages.
    algs: list of algorithms to compute.
    file_name: file to digest.
    src_obj_metadata: metadta of source object.

  Returns:
    Dict of algorithm name : base 64 encoded digest
  """
  hash_dict = {}
  if 'md5' in algs:
    if src_obj_metadata.size and src_obj_metadata.size > TEN_MIB:
      logger.info(
          'Computing MD5 for %s...', file_name)
    hash_dict['md5'] = md5()
  if 'crc32c' in algs:
    hash_dict['crc32c'] = crcmod.predefined.Crc('crc-32c')
  with open(file_name, 'rb') as fp:
    CalculateHashesFromContents(
        fp, hash_dict, ProgressCallbackWithBackoff(
            src_obj_metadata.size,
            FileProgressCallbackHandler(
                ConstructAnnounceText('Hashing', file_name), logger).call))
  digests = {}
  for alg_name, digest in hash_dict.iteritems():
    digests[alg_name] = Base64EncodeHash(digest.hexdigest())
  return digests


def _CheckCloudHashes(logger, src_url, dst_url, src_obj_metadata,
                      dst_obj_metadata):
  """Validates integrity of two cloud objects copied via daisy-chain.

  Args:
    logger: for outputting log messages.
    src_url: CloudUrl for source cloud object.
    dst_url: CloudUrl for destination cloud object.
    src_obj_metadata: Cloud Object metadata for object being downloaded from.
    dst_obj_metadata: Cloud Object metadata for object being uploaded to.

  Raises:
    CommandException: if cloud digests don't match local digests.
  """
  checked_one = False
  download_hashes = {}
  upload_hashes = {}
  if src_obj_metadata.md5Hash:
    download_hashes['md5'] = src_obj_metadata.md5Hash
  if src_obj_metadata.crc32c:
    download_hashes['crc32c'] = src_obj_metadata.crc32c
  if dst_obj_metadata.md5Hash:
    upload_hashes['md5'] = dst_obj_metadata.md5Hash
  if dst_obj_metadata.crc32c:
    upload_hashes['crc32c'] = dst_obj_metadata.crc32c

  for alg, upload_b64_digest in upload_hashes.iteritems():
    if alg not in download_hashes:
      continue

    download_b64_digest = download_hashes[alg]
    logger.debug(
        'Comparing source vs destination %s-checksum for %s. (%s/%s)', alg,
        dst_url, download_b64_digest, upload_b64_digest)
    if download_b64_digest != upload_b64_digest:
      raise HashMismatchException(
          '%s signature for source object (%s) doesn\'t match '
          'destination object digest (%s). Object (%s) will be deleted.' % (
              alg, download_b64_digest, upload_b64_digest, dst_url))
    checked_one = True
  if not checked_one:
    # One known way this can currently happen is when downloading objects larger
    # than 5 GiB from S3 (for which the etag is not an MD5).
    logger.warn(
        'WARNING: Found no hashes to validate object downloaded from %s and '
        'uploaded to %s. Integrity cannot be assured without hashes.',
        src_url, dst_url)


def _CheckHashes(logger, obj_url, obj_metadata, file_name, digests,
                 is_upload=False):
  """Validates integrity by comparing cloud digest to local digest.

  Args:
    logger: for outputting log messages.
    obj_url: CloudUrl for cloud object.
    obj_metadata: Cloud Object being downloaded from or uploaded to.
    file_name: Local file name on disk being downloaded to or uploaded from.
    digests: Computed Digests for the object.
    is_upload: If true, comparing for an uploaded object (controls logging).

  Raises:
    CommandException: if cloud digests don't match local digests.
  """
  local_hashes = digests
  cloud_hashes = {}
  if obj_metadata.md5Hash:
    cloud_hashes['md5'] = obj_metadata.md5Hash.rstrip('\n')
  if obj_metadata.crc32c:
    cloud_hashes['crc32c'] = obj_metadata.crc32c.rstrip('\n')

  checked_one = False
  for alg in local_hashes:
    if alg not in cloud_hashes:
      continue

    local_b64_digest = local_hashes[alg]
    cloud_b64_digest = cloud_hashes[alg]
    logger.debug(
        'Comparing local vs cloud %s-checksum for %s. (%s/%s)', alg, file_name,
        local_b64_digest, cloud_b64_digest)
    if local_b64_digest != cloud_b64_digest:

      raise HashMismatchException(
          '%s signature computed for local file (%s) doesn\'t match '
          'cloud-supplied digest (%s). %s (%s) will be deleted.' % (
              alg, local_b64_digest, cloud_b64_digest,
              'Cloud object' if is_upload else 'Local file',
              obj_url if is_upload else file_name))
    checked_one = True
  if not checked_one:
    if is_upload:
      logger.warn(
          'WARNING: Found no hashes to validate object uploaded to %s. '
          'Integrity cannot be assured without hashes.', obj_url)
    else:
    # One known way this can currently happen is when downloading objects larger
    # than 5 GB from S3 (for which the etag is not an MD5).
      logger.warn(
          'WARNING: Found no hashes to validate object downloaded to %s. '
          'Integrity cannot be assured without hashes.', file_name)


def IsNoClobberServerException(e):
  """Checks to see if the server attempted to clobber a file.

  In this case we specified via a precondition that we didn't want the file
  clobbered.

  Args:
    e: The Exception that was generated by a failed copy operation

  Returns:
    bool indicator - True indicates that the server did attempt to clobber
        an existing file.
  """
  return ((isinstance(e, PreconditionException)) or
          (isinstance(e, ResumableUploadException) and '412' in e.message))


def CheckForDirFileConflict(exp_src_url, dst_url):
  """Checks whether copying exp_src_url into dst_url is not possible.

     This happens if a directory exists in local file system where a file
     needs to go or vice versa. In that case we print an error message and
     exits. Example: if the file "./x" exists and you try to do:
       gsutil cp gs://mybucket/x/y .
     the request can't succeed because it requires a directory where
     the file x exists.

     Note that we don't enforce any corresponding restrictions for buckets,
     because the flat namespace semantics for buckets doesn't prohibit such
     cases the way hierarchical file systems do. For example, if a bucket
     contains an object called gs://bucket/dir and then you run the command:
       gsutil cp file1 file2 gs://bucket/dir
     you'll end up with objects gs://bucket/dir, gs://bucket/dir/file1, and
     gs://bucket/dir/file2.

  Args:
    exp_src_url: Expanded source StorageUrl.
    dst_url: Destination StorageUrl.

  Raises:
    CommandException: if errors encountered.
  """
  if dst_url.IsCloudUrl():
    # The problem can only happen for file destination URLs.
    return
  dst_path = dst_url.object_name
  final_dir = os.path.dirname(dst_path)
  if os.path.isfile(final_dir):
    raise CommandException('Cannot retrieve %s because a file exists '
                           'where a directory needs to be created (%s).' %
                           (exp_src_url.url_string, final_dir))
  if os.path.isdir(dst_path):
    raise CommandException('Cannot retrieve %s because a directory exists '
                           '(%s) where the file needs to be created.' %
                           (exp_src_url.url_string, dst_path))


def _PartitionFile(fp, file_size, src_url, content_type, canned_acl,
                   dst_bucket_url, random_prefix, tracker_file,
                   tracker_file_lock):
  """Partitions a file into FilePart objects to be uploaded and later composed.

  These objects, when composed, will match the original file. This entails
  splitting the file into parts, naming and forming a destination URL for each
  part, and also providing the PerformParallelUploadFileToObjectArgs
  corresponding to each part.

  Args:
    fp: The file object to be partitioned.
    file_size: The size of fp, in bytes.
    src_url: Source FileUrl from the original command.
    content_type: content type for the component and final objects.
    canned_acl: The user-provided canned_acl, if applicable.
    dst_bucket_url: CloudUrl for the destination bucket
    random_prefix: The randomly-generated prefix used to prevent collisions
                   among the temporary component names.
    tracker_file: The path to the parallel composite upload tracker file.
    tracker_file_lock: The lock protecting access to the tracker file.

  Returns:
    dst_args: The destination URIs for the temporary component objects.
  """
  parallel_composite_upload_component_size = HumanReadableToBytes(
      config.get('GSUtil', 'parallel_composite_upload_component_size',
                 DEFAULT_PARALLEL_COMPOSITE_UPLOAD_COMPONENT_SIZE))
  (num_components, component_size) = _GetPartitionInfo(
      file_size, MAX_COMPOSE_ARITY, parallel_composite_upload_component_size)

  dst_args = {}  # Arguments to create commands and pass to subprocesses.
  file_names = []  # Used for the 2-step process of forming dst_args.
  for i in range(num_components):
    # "Salt" the object name with something a user is very unlikely to have
    # used in an object name, then hash the extended name to make sure
    # we don't run into problems with name length. Using a deterministic
    # naming scheme for the temporary components allows users to take
    # advantage of resumable uploads for each component.
    encoded_name = (PARALLEL_UPLOAD_STATIC_SALT + fp.name).encode(UTF8)
    content_md5 = md5()
    content_md5.update(encoded_name)
    digest = content_md5.hexdigest()
    temp_file_name = (random_prefix + PARALLEL_UPLOAD_TEMP_NAMESPACE +
                      digest + '_' + str(i))
    tmp_dst_url = dst_bucket_url.Clone()
    tmp_dst_url.object_name = temp_file_name

    if i < (num_components - 1):
      # Every component except possibly the last is the same size.
      file_part_length = component_size
    else:
      # The last component just gets all of the remaining bytes.
      file_part_length = (file_size - ((num_components -1) * component_size))
    offset = i * component_size
    func_args = PerformParallelUploadFileToObjectArgs(
        fp.name, offset, file_part_length, src_url, tmp_dst_url, canned_acl,
        content_type, tracker_file, tracker_file_lock)
    file_names.append(temp_file_name)
    dst_args[temp_file_name] = func_args

  return dst_args


def _DoParallelCompositeUpload(fp, src_url, dst_url, dst_obj_metadata,
                               canned_acl, file_size, preconditions, gsutil_api,
                               command_obj, copy_exception_handler):
  """Uploads a local file to a cloud object using parallel composite upload.

  The file is partitioned into parts, and then the parts are uploaded in
  parallel, composed to form the original destination object, and deleted.

  Args:
    fp: The file object to be uploaded.
    src_url: FileUrl representing the local file.
    dst_url: CloudUrl representing the destination file.
    dst_obj_metadata: apitools Object describing the destination object.
    canned_acl: The canned acl to apply to the object, if any.
    file_size: The size of the source file in bytes.
    preconditions: Cloud API Preconditions for the final object.
    gsutil_api: gsutil Cloud API instance to use.
    command_obj: Command object (for calling Apply).
    copy_exception_handler: Copy exception handler (for use in Apply).

  Returns:
    Elapsed upload time, uploaded Object with generation, crc32c, and size
    fields populated.
  """
  start_time = time.time()
  dst_bucket_url = StorageUrlFromString(dst_url.bucket_url_string)
  api_selector = gsutil_api.GetApiSelector(provider=dst_url.scheme)
  # Determine which components, if any, have already been successfully
  # uploaded.
  tracker_file = GetTrackerFilePath(dst_url, TrackerFileType.PARALLEL_UPLOAD,
                                    api_selector, src_url)
  tracker_file_lock = CreateLock()
  (random_prefix, existing_components) = (
      _ParseParallelUploadTrackerFile(tracker_file, tracker_file_lock))

  # Create the initial tracker file for the upload.
  _CreateParallelUploadTrackerFile(tracker_file, random_prefix,
                                   existing_components, tracker_file_lock)

  # Get the set of all components that should be uploaded.
  dst_args = _PartitionFile(
      fp, file_size, src_url, dst_obj_metadata.contentType, canned_acl,
      dst_bucket_url, random_prefix, tracker_file, tracker_file_lock)

  (components_to_upload, existing_components, existing_objects_to_delete) = (
      FilterExistingComponents(dst_args, existing_components, dst_bucket_url,
                               gsutil_api))

  # In parallel, copy all of the file parts that haven't already been
  # uploaded to temporary objects.
  cp_results = command_obj.Apply(
      _PerformParallelUploadFileToObject, components_to_upload,
      copy_exception_handler, ('op_failure_count', 'total_bytes_transferred'),
      arg_checker=gslib.command.DummyArgChecker,
      parallel_operations_override=True, should_return_results=True)
  uploaded_components = []
  for cp_result in cp_results:
    uploaded_components.append(cp_result[2])
  components = uploaded_components + existing_components

  if len(components) == len(dst_args):
    # Only try to compose if all of the components were uploaded successfully.

    def _GetComponentNumber(component):
      return int(component.object_name[component.object_name.rfind('_')+1:])
    # Sort the components so that they will be composed in the correct order.
    components = sorted(components, key=_GetComponentNumber)

    request_components = []
    for component_url in components:
      src_obj_metadata = (
          apitools_messages.ComposeRequest.SourceObjectsValueListEntry(
              name=component_url.object_name))
      if component_url.HasGeneration():
        src_obj_metadata.generation = long(component_url.generation)
      request_components.append(src_obj_metadata)

    composed_object = gsutil_api.ComposeObject(
        request_components, dst_obj_metadata, preconditions=preconditions,
        provider=dst_url.scheme, fields=['generation', 'crc32c', 'size'])

    try:
      # Make sure only to delete things that we know were successfully
      # uploaded (as opposed to all of the objects that we attempted to
      # create) so that we don't delete any preexisting objects, except for
      # those that were uploaded by a previous, failed run and have since
      # changed (but still have an old generation lying around).
      objects_to_delete = components + existing_objects_to_delete
      command_obj.Apply(_DeleteObjectFn, objects_to_delete, _RmExceptionHandler,
                        arg_checker=gslib.command.DummyArgChecker,
                        parallel_operations_override=True)
    except Exception:  # pylint: disable=broad-except
      # If some of the delete calls fail, don't cause the whole command to
      # fail. The copy was successful iff the compose call succeeded, so
      # reduce this to a warning.
      logging.warning(
          'Failed to delete some of the following temporary objects:\n' +
          '\n'.join(dst_args.keys()))
    finally:
      with tracker_file_lock:
        if os.path.exists(tracker_file):
          os.unlink(tracker_file)
  else:
    # Some of the components failed to upload. In this case, we want to exit
    # without deleting the objects.
    raise CommandException(
        'Some temporary components were not uploaded successfully. '
        'Please retry this upload.')

  elapsed_time = time.time() - start_time
  return elapsed_time, composed_object


def _ShouldDoParallelCompositeUpload(logger, allow_splitting, src_url, dst_url,
                                     file_size, canned_acl=None):
  """Determines whether parallel composite upload strategy should be used.

  Args:
    logger: for outputting log messages.
    allow_splitting: If false, then this function returns false.
    src_url: FileUrl corresponding to a local file.
    dst_url: CloudUrl corresponding to destination cloud object.
    file_size: The size of the source file, in bytes.
    canned_acl: Canned ACL to apply to destination object, if any.

  Returns:
    True iff a parallel upload should be performed on the source file.
  """
  global suggested_parallel_composites
  parallel_composite_upload_threshold = HumanReadableToBytes(config.get(
      'GSUtil', 'parallel_composite_upload_threshold',
      DEFAULT_PARALLEL_COMPOSITE_UPLOAD_THRESHOLD))

  all_factors_but_size = (
      allow_splitting  # Don't split the pieces multiple times.
      and not src_url.IsStream()  # We can't partition streams.
      and dst_url.scheme == 'gs'  # Compose is only for gs.
      and not canned_acl)  # TODO: Implement canned ACL support for compose.

  # Since parallel composite uploads are disabled by default, make user aware of
  # them.
  # TODO: Once compiled crcmod is being distributed by major Linux distributions
  # remove this check.
  if (all_factors_but_size and parallel_composite_upload_threshold == 0
      and file_size >= PARALLEL_COMPOSITE_SUGGESTION_THRESHOLD
      and not suggested_parallel_composites):
    logger.info('\n'.join(textwrap.wrap(
        '==> NOTE: You are uploading one or more large file(s), which would '
        'run significantly faster if you enable parallel composite uploads. '
        'This feature can be enabled by editing the '
        '"parallel_composite_upload_threshold" value in your .boto '
        'configuration file. However, note that if you do this you and any '
        'users that download such composite files will need to have a compiled '
        'crcmod installed (see "gsutil help crcmod").')) + '\n')
    suggested_parallel_composites = True

  return (all_factors_but_size
          and parallel_composite_upload_threshold > 0
          and file_size >= parallel_composite_upload_threshold)


def ExpandUrlToSingleBlr(url_str, gsutil_api, debug, project_id,
                         treat_nonexistent_object_as_subdir=False):
  """Expands wildcard if present in url_str.

  Args:
    url_str: String representation of requested url.
    gsutil_api: gsutil Cloud API instance to use.
    debug: debug level to use (for iterators).
    project_id: project ID to use (for iterators).
    treat_nonexistent_object_as_subdir: indicates if should treat a non-existent
                                        object as a subdir.

  Returns:
      (exp_url, have_existing_dst_container)
      where exp_url is a StorageUrl
      and have_existing_dst_container is a bool indicating whether
      exp_url names an existing directory, bucket, or bucket subdirectory.
      In the case where we match a subdirectory AND an object, the
      object is returned.

  Raises:
    CommandException: if url_str matched more than 1 URL.
  """
  # Handle wildcarded url case.
  if ContainsWildcard(url_str):
    blr_expansion = list(CreateWildcardIterator(url_str, gsutil_api,
                                                debug=debug,
                                                project_id=project_id))
    if len(blr_expansion) != 1:
      raise CommandException('Destination (%s) must match exactly 1 URL' %
                             url_str)
    blr = blr_expansion[0]
    # BLR is either an OBJECT, PREFIX, or BUCKET; the latter two represent
    # directories.
    return (StorageUrlFromString(blr.url_string), not blr.IsObject())

  storage_url = StorageUrlFromString(url_str)

  # Handle non-wildcarded URL.
  if storage_url.IsFileUrl():
    return (storage_url, storage_url.IsDirectory())

  # At this point we have a cloud URL.
  if storage_url.IsBucket():
    return (storage_url, True)

  # For object/prefix URLs check 3 cases: (a) if the name ends with '/' treat
  # as a subdir; otherwise, use the wildcard iterator with url to
  # find if (b) there's a Prefix matching url, or (c) name is of form
  # dir_$folder$ (and in both these cases also treat dir as a subdir).
  # Cloud subdirs are always considered to be an existing container.
  if IsCloudSubdirPlaceholder(storage_url):
    return (storage_url, True)

  # Check for the special case where we have a folder marker object.
  folder_expansion = CreateWildcardIterator(
      storage_url.versionless_url_string + '_$folder$', gsutil_api,
      debug=debug, project_id=project_id).IterAll(
          bucket_listing_fields=['name'])
  for blr in folder_expansion:
    return (storage_url, True)

  blr_expansion = CreateWildcardIterator(url_str, gsutil_api,
                                         debug=debug,
                                         project_id=project_id).IterAll(
                                             bucket_listing_fields=['name'])
  expansion_empty = True
  for blr in blr_expansion:
    expansion_empty = False
    if blr.IsPrefix():
      return (storage_url, True)

  return (storage_url,
          expansion_empty and treat_nonexistent_object_as_subdir)


def FixWindowsNaming(src_url, dst_url):
  """Translates Windows pathnames to cloud pathnames.

  Rewrites the destination URL built by ConstructDstUrl().

  Args:
    src_url: Source StorageUrl to be copied.
    dst_url: The destination StorageUrl built by ConstructDstUrl().

  Returns:
    StorageUrl to use for copy.
  """
  if (src_url.IsFileUrl() and src_url.delim == '\\'
      and dst_url.IsCloudUrl()):
    trans_url_str = re.sub(r'\\', '/', dst_url.url_string)
    dst_url = StorageUrlFromString(trans_url_str)
  return dst_url


def SrcDstSame(src_url, dst_url):
  """Checks if src_url and dst_url represent the same object or file.

  We don't handle anything about hard or symbolic links.

  Args:
    src_url: Source StorageUrl.
    dst_url: Destination StorageUrl.

  Returns:
    Bool indicator.
  """
  if src_url.IsFileUrl() and dst_url.IsFileUrl():
    # Translate a/b/./c to a/b/c, so src=dst comparison below works.
    new_src_path = os.path.normpath(src_url.object_name)
    new_dst_path = os.path.normpath(dst_url.object_name)
    return new_src_path == new_dst_path
  else:
    return (src_url.url_string == dst_url.url_string and
            src_url.generation == dst_url.generation)


def _LogCopyOperation(logger, src_url, dst_url, dst_obj_metadata):
  """Logs copy operation, including Content-Type if appropriate.

  Args:
    logger: logger instance to use for output.
    src_url: Source StorageUrl.
    dst_url: Destination StorageUrl.
    dst_obj_metadata: Object-specific metadata that should be overidden during
                      the copy.
  """
  if (dst_url.IsCloudUrl() and dst_obj_metadata and
      dst_obj_metadata.contentType):
    content_type_msg = ' [Content-Type=%s]' % dst_obj_metadata.contentType
  else:
    content_type_msg = ''
  if src_url.IsFileUrl() and src_url.IsStream():
    logger.info('Copying from <STDIN>%s...', content_type_msg)
  else:
    logger.info('Copying %s%s...', src_url.url_string, content_type_msg)


# pylint: disable=undefined-variable
def _CopyObjToObjInTheCloud(src_url, src_obj_metadata, dst_url,
                            dst_obj_metadata, preconditions, gsutil_api,
                            logger):
  """Performs copy-in-the cloud from specified src to dest object.

  Args:
    src_url: Source CloudUrl.
    src_obj_metadata: Metadata for source object; must include etag and size.
    dst_url: Destination CloudUrl.
    dst_obj_metadata: Object-specific metadata that should be overidden during
                      the copy.
    preconditions: Preconditions to use for the copy.
    gsutil_api: gsutil Cloud API instance to use for the copy.
    logger: logging.Logger for log message output.

  Returns:
    (elapsed_time, bytes_transferred, dst_url with generation,
    md5 hash of destination) excluding overhead like initial GET.

  Raises:
    CommandException: if errors encountered.
  """
  start_time = time.time()

  progress_callback = FileProgressCallbackHandler(
      ConstructAnnounceText('Copying', dst_url.url_string), logger).call
  if global_copy_helper_opts.test_callback_file:
    with open(global_copy_helper_opts.test_callback_file, 'rb') as test_fp:
      progress_callback = pickle.loads(test_fp.read()).call
  dst_obj = gsutil_api.CopyObject(
      src_obj_metadata, dst_obj_metadata, src_generation=src_url.generation,
      canned_acl=global_copy_helper_opts.canned_acl,
      preconditions=preconditions, progress_callback=progress_callback,
      provider=dst_url.scheme, fields=UPLOAD_RETURN_FIELDS)

  end_time = time.time()

  result_url = dst_url.Clone()
  result_url.generation = GenerationFromUrlAndString(result_url,
                                                     dst_obj.generation)

  return (end_time - start_time, src_obj_metadata.size, result_url,
          dst_obj.md5Hash)


def _CheckFreeSpace(path):
  """Return path/drive free space (in bytes)."""
  if IS_WINDOWS:
    # pylint: disable=g-import-not-at-top
    try:
      # pylint: disable=invalid-name
      get_disk_free_space_ex = WINFUNCTYPE(c_int, c_wchar_p,
                                           POINTER(c_uint64),
                                           POINTER(c_uint64),
                                           POINTER(c_uint64))
      get_disk_free_space_ex = get_disk_free_space_ex(
          ('GetDiskFreeSpaceExW', windll.kernel32), (
              (1, 'lpszPathName'),
              (2, 'lpFreeUserSpace'),
              (2, 'lpTotalSpace'),
              (2, 'lpFreeSpace'),))
    except AttributeError:
      get_disk_free_space_ex = WINFUNCTYPE(c_int, c_char_p,
                                           POINTER(c_uint64),
                                           POINTER(c_uint64),
                                           POINTER(c_uint64))
      get_disk_free_space_ex = get_disk_free_space_ex(
          ('GetDiskFreeSpaceExA', windll.kernel32), (
              (1, 'lpszPathName'),
              (2, 'lpFreeUserSpace'),
              (2, 'lpTotalSpace'),
              (2, 'lpFreeSpace'),))

    def GetDiskFreeSpaceExErrCheck(result, unused_func, args):
      if not result:
        raise WinError()
      return args[1].value
    get_disk_free_space_ex.errcheck = GetDiskFreeSpaceExErrCheck

    return get_disk_free_space_ex(os.getenv('SystemDrive'))
  else:
    (_, f_frsize, _, _, f_bavail, _, _, _, _, _) = os.statvfs(path)
    return f_frsize * f_bavail


def _SetContentTypeFromFile(src_url, dst_obj_metadata):
  """Detects and sets Content-Type if src_url names a local file.

  Args:
    src_url: Source StorageUrl.
    dst_obj_metadata: Object-specific metadata that should be overidden during
                     the copy.
  """
  # contentType == '' if user requested default type.
  if (dst_obj_metadata.contentType is None and src_url.IsFileUrl()
      and not src_url.IsStream()):
    # Only do content type recognition if src_url is a file. Object-to-object
    # copies with no -h Content-Type specified re-use the content type of the
    # source object.
    object_name = src_url.object_name
    content_type = None
    # Streams (denoted by '-') are expected to be 'application/octet-stream'
    # and 'file' would partially consume them.
    if object_name != '-':
      if config.getbool('GSUtil', 'use_magicfile', False):
        p = subprocess.Popen(['file', '--mime-type', object_name],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = p.communicate()
        p.stdout.close()
        p.stderr.close()
        if p.returncode != 0 or error:
          raise CommandException(
              'Encountered error running "file --mime-type %s" '
              '(returncode=%d).\n%s' % (object_name, p.returncode, error))
        # Parse output by removing line delimiter and splitting on last ":
        content_type = output.rstrip().rpartition(': ')[2]
      else:
        content_type = mimetypes.guess_type(object_name)[0]
    if not content_type:
      content_type = DEFAULT_CONTENT_TYPE
    dst_obj_metadata.contentType = content_type


# pylint: disable=undefined-variable
def _UploadFileToObjectNonResumable(src_url, src_obj_filestream,
                                    src_obj_size, dst_url, dst_obj_metadata,
                                    preconditions, gsutil_api, logger):
  """Uploads the file using a non-resumable strategy.

  Args:
    src_url: Source StorageUrl to upload.
    src_obj_filestream: File pointer to uploadable bytes.
    src_obj_size: Size of the source object.
    dst_url: Destination StorageUrl for the upload.
    dst_obj_metadata: Metadata for the target object.
    preconditions: Preconditions for the upload, if any.
    gsutil_api: gsutil Cloud API instance to use for the upload.
    logger: For outputting log messages.

  Returns:
    Elapsed upload time, uploaded Object with generation, md5, and size fields
    populated.
  """
  progress_callback = FileProgressCallbackHandler(
      ConstructAnnounceText('Uploading', dst_url.url_string), logger).call
  if global_copy_helper_opts.test_callback_file:
    with open(global_copy_helper_opts.test_callback_file, 'rb') as test_fp:
      progress_callback = pickle.loads(test_fp.read()).call
  start_time = time.time()

  if src_url.IsStream():
    # TODO: gsutil-beta: Provide progress callbacks for streaming uploads.
    uploaded_object = gsutil_api.UploadObjectStreaming(
        src_obj_filestream, object_metadata=dst_obj_metadata,
        canned_acl=global_copy_helper_opts.canned_acl,
        preconditions=preconditions, progress_callback=progress_callback,
        provider=dst_url.scheme, fields=UPLOAD_RETURN_FIELDS)
  else:
    uploaded_object = gsutil_api.UploadObject(
        src_obj_filestream, object_metadata=dst_obj_metadata,
        canned_acl=global_copy_helper_opts.canned_acl, size=src_obj_size,
        preconditions=preconditions, progress_callback=progress_callback,
        provider=dst_url.scheme, fields=UPLOAD_RETURN_FIELDS)
  end_time = time.time()
  elapsed_time = end_time - start_time

  return elapsed_time, uploaded_object


# pylint: disable=undefined-variable
def _UploadFileToObjectResumable(src_url, src_obj_filestream,
                                 src_obj_size, dst_url, dst_obj_metadata,
                                 preconditions, gsutil_api, logger):
  """Uploads the file using a resumable strategy.

  Args:
    src_url: Source FileUrl to upload.  Must not be a stream.
    src_obj_filestream: File pointer to uploadable bytes.
    src_obj_size: Size of the source object.
    dst_url: Destination StorageUrl for the upload.
    dst_obj_metadata: Metadata for the target object.
    preconditions: Preconditions for the upload, if any.
    gsutil_api: gsutil Cloud API instance to use for the upload.
    logger: for outputting log messages.

  Returns:
    Elapsed upload time, uploaded Object with generation, md5, and size fields
    populated.
  """
  tracker_file_name = GetTrackerFilePath(
      dst_url, TrackerFileType.UPLOAD,
      gsutil_api.GetApiSelector(provider=dst_url.scheme))

  def _UploadTrackerCallback(serialization_data):
    """Creates a new tracker file for starting an upload from scratch.

    This function is called by the gsutil Cloud API implementation and the
    the serialization data is implementation-specific.

    Args:
      serialization_data: Serialization data used in resuming the upload.
    """
    tracker_file = None
    try:
      tracker_file = open(tracker_file_name, 'w')
      tracker_file.write(str(serialization_data))
    except IOError as e:
      RaiseUnwritableTrackerFileException(tracker_file_name, e.strerror)
    finally:
      if tracker_file:
        tracker_file.close()

  # This contains the upload URL, which will uniquely identify the
  # destination object.
  tracker_data = _GetUploadTrackerData(tracker_file_name, logger)
  if tracker_data:
    logger.info(
        'Resuming upload for %s', src_url.url_string)

  retryable = True

  progress_callback = FileProgressCallbackHandler(
      ConstructAnnounceText('Uploading', dst_url.url_string), logger).call
  if global_copy_helper_opts.test_callback_file:
    with open(global_copy_helper_opts.test_callback_file, 'rb') as test_fp:
      progress_callback = pickle.loads(test_fp.read()).call

  start_time = time.time()
  num_startover_attempts = 0
  # This loop causes us to retry when the resumable upload failed in a way that
  # requires starting over with a new upload ID. Retries within a single upload
  # ID within the current process are handled in
  # gsutil_api.UploadObjectResumable, and retries within a single upload ID
  # spanning processes happens if an exception occurs not caught below (which
  # will leave the tracker file in place, and cause the upload ID to be reused
  # the next time the user runs gsutil and attempts the same upload).
  while retryable:
    try:
      uploaded_object = gsutil_api.UploadObjectResumable(
          src_obj_filestream, object_metadata=dst_obj_metadata,
          canned_acl=global_copy_helper_opts.canned_acl,
          preconditions=preconditions, provider=dst_url.scheme,
          size=src_obj_size, serialization_data=tracker_data,
          fields=UPLOAD_RETURN_FIELDS,
          tracker_callback=_UploadTrackerCallback,
          progress_callback=progress_callback)
      retryable = False
    except ResumableUploadStartOverException, e:
      # This can happen, for example, if the server sends a 410 response code.
      # In that case the current resumable upload ID can't be reused, so delete
      # the tracker file and try again up to max retries.
      num_startover_attempts += 1
      retryable = (num_startover_attempts < GetNumRetries())
      if not retryable:
        raise

      # If the server sends a 404 response code, then the upload should only
      # be restarted if it was the object (and not the bucket) that was missing.
      try:
        gsutil_api.GetBucket(dst_obj_metadata.bucket, provider=dst_url.scheme)
      except NotFoundException:
        raise

      logger.info('Restarting upload from scratch after exception %s', e)
      DeleteTrackerFile(tracker_file_name)
      tracker_data = None
      src_obj_filestream.seek(0)
      # Reset the progress callback handler.
      progress_callback = FileProgressCallbackHandler(
          ConstructAnnounceText('Uploading', dst_url.url_string), logger).call
      logger.info('\n'.join(textwrap.wrap(
          'Resumable upload of %s failed with a response code indicating we '
          'need to start over with a new resumable upload ID. Backing off '
          'and retrying.' % src_url.url_string)))
      time.sleep(min(random.random() * (2 ** num_startover_attempts),
                     GetMaxRetryDelay()))
    except ResumableUploadAbortException:
      retryable = False
      raise
    finally:
      if not retryable:
        DeleteTrackerFile(tracker_file_name)

  end_time = time.time()
  elapsed_time = end_time - start_time

  return (elapsed_time, uploaded_object)


def _CompressFileForUpload(src_url, src_obj_filestream, src_obj_size, logger):
  """Compresses a to-be-uploaded local file to save bandwidth.

  Args:
    src_url: Source FileUrl.
    src_obj_filestream: Read stream of the source file - will be consumed
                        and closed.
    src_obj_size: Size of the source file.
    logger: for outputting log messages.

  Returns:
    StorageUrl path to compressed file, compressed file size.
  """
  # TODO: Compress using a streaming model as opposed to all at once here.
  if src_obj_size >= MIN_SIZE_COMPUTE_LOGGING:
    logger.info(
        'Compressing %s (to tmp)...', src_url)
  (gzip_fh, gzip_path) = tempfile.mkstemp()
  gzip_fp = None
  try:
    # Check for temp space. Assume the compressed object is at most 2x
    # the size of the object (normally should compress to smaller than
    # the object)
    if _CheckFreeSpace(gzip_path) < 2*int(src_obj_size):
      raise CommandException('Inadequate temp space available to compress '
                             '%s. See the CHANGING TEMP DIRECTORIES section '
                             'of "gsutil help cp" for more info.' % src_url)
    gzip_fp = gzip.open(gzip_path, 'wb')
    data = src_obj_filestream.read(GZIP_CHUNK_SIZE)
    while data:
      gzip_fp.write(data)
      data = src_obj_filestream.read(GZIP_CHUNK_SIZE)
  finally:
    if gzip_fp:
      gzip_fp.close()
    os.close(gzip_fh)
    src_obj_filestream.close()
  gzip_size = os.path.getsize(gzip_path)
  return StorageUrlFromString(gzip_path), gzip_size


def _UploadFileToObject(src_url, src_obj_filestream, src_obj_size,
                        dst_url, dst_obj_metadata, preconditions, gsutil_api,
                        logger, command_obj, copy_exception_handler,
                        gzip_exts=None, allow_splitting=True):
  """Uploads a local file to an object.

  Args:
    src_url: Source FileUrl.
    src_obj_filestream: Read stream of the source file to be read and closed.
    src_obj_size: Size of the source file.
    dst_url: Destination CloudUrl.
    dst_obj_metadata: Metadata to be applied to the destination object.
    preconditions: Preconditions to use for the copy.
    gsutil_api: gsutil Cloud API to use for the copy.
    logger: for outputting log messages.
    command_obj: command object for use in Apply in parallel composite uploads.
    copy_exception_handler: For handling copy exceptions during Apply.
    gzip_exts: List of file extensions to gzip prior to upload, if any.
    allow_splitting: Whether to allow the file to be split into component
                     pieces for an parallel composite upload.

  Returns:
    (elapsed_time, bytes_transferred, dst_url with generation,
    md5 hash of destination) excluding overhead like initial GET.

  Raises:
    CommandException: if errors encountered.
  """
  if not dst_obj_metadata or not dst_obj_metadata.contentLanguage:
    content_language = config.get_value('GSUtil', 'content_language')
    if content_language:
      dst_obj_metadata.contentLanguage = content_language

  fname_parts = src_url.object_name.split('.')
  upload_url = src_url
  upload_stream = src_obj_filestream
  upload_size = src_obj_size
  zipped_file = False
  if gzip_exts and len(fname_parts) > 1 and fname_parts[-1] in gzip_exts:
    upload_url, upload_size = _CompressFileForUpload(
        src_url, src_obj_filestream, src_obj_size, logger)
    upload_stream = open(upload_url.object_name, 'rb')
    dst_obj_metadata.contentEncoding = 'gzip'
    zipped_file = True

  elapsed_time = None
  uploaded_object = None
  hash_algs = GetUploadHashAlgs()
  digesters = dict((alg, hash_algs[alg]()) for alg in hash_algs or {})

  parallel_composite_upload = _ShouldDoParallelCompositeUpload(
      logger, allow_splitting, upload_url, dst_url, src_obj_size,
      canned_acl=global_copy_helper_opts.canned_acl)

  if (src_url.IsStream() and
      gsutil_api.GetApiSelector(provider=dst_url.scheme) == ApiSelector.JSON):
    orig_stream = upload_stream
    # Add limited seekable properties to the stream via buffering.
    upload_stream = ResumableStreamingJsonUploadWrapper(
        orig_stream, GetJsonResumableChunkSize())

  if not parallel_composite_upload and len(hash_algs):
    # Parallel composite uploads calculate hashes per-component in subsequent
    # calls to this function, but the composition of the final object is a
    # cloud-only operation.
    wrapped_filestream = HashingFileUploadWrapper(upload_stream, digesters,
                                                  hash_algs, upload_url, logger)
  else:
    wrapped_filestream = upload_stream

  try:
    if parallel_composite_upload:
      elapsed_time, uploaded_object = _DoParallelCompositeUpload(
          upload_stream, upload_url, dst_url, dst_obj_metadata,
          global_copy_helper_opts.canned_acl, upload_size, preconditions,
          gsutil_api, command_obj, copy_exception_handler)
    elif upload_size < ResumableThreshold() or src_url.IsStream():
      elapsed_time, uploaded_object = _UploadFileToObjectNonResumable(
          upload_url, wrapped_filestream, upload_size, dst_url,
          dst_obj_metadata, preconditions, gsutil_api, logger)
    else:
      elapsed_time, uploaded_object = _UploadFileToObjectResumable(
          upload_url, wrapped_filestream, upload_size, dst_url,
          dst_obj_metadata, preconditions, gsutil_api, logger)

  finally:
    if zipped_file:
      try:
        os.unlink(upload_url.object_name)
      # Windows sometimes complains the temp file is locked when you try to
      # delete it.
      except Exception:  # pylint: disable=broad-except
        logger.warning(
            'Could not delete %s. This can occur in Windows because the '
            'temporary file is still locked.', upload_url.object_name)
    # In the gzip case, this is the gzip stream.  _CompressFileForUpload will
    # have already closed the original source stream.
    upload_stream.close()

  if not parallel_composite_upload:
    try:
      digests = _CreateDigestsFromDigesters(digesters)
      _CheckHashes(logger, dst_url, uploaded_object, src_url.object_name,
                   digests, is_upload=True)
    except HashMismatchException:
      if _RENAME_ON_HASH_MISMATCH:
        corrupted_obj_metadata = apitools_messages.Object(
            name=dst_obj_metadata.name,
            bucket=dst_obj_metadata.bucket,
            etag=uploaded_object.etag)
        dst_obj_metadata.name = (dst_url.object_name +
                                 _RENAME_ON_HASH_MISMATCH_SUFFIX)
        gsutil_api.CopyObject(corrupted_obj_metadata,
                              dst_obj_metadata, provider=dst_url.scheme)
      # If the digest doesn't match, delete the object.
      gsutil_api.DeleteObject(dst_url.bucket_name, dst_url.object_name,
                              generation=uploaded_object.generation,
                              provider=dst_url.scheme)
      raise

  result_url = dst_url.Clone()

  result_url.generation = uploaded_object.generation
  result_url.generation = GenerationFromUrlAndString(
      result_url, uploaded_object.generation)

  return (elapsed_time, uploaded_object.size, result_url,
          uploaded_object.md5Hash)


# TODO: Refactor this long function into smaller pieces.
# pylint: disable=too-many-statements
def _DownloadObjectToFile(src_url, src_obj_metadata, dst_url,
                          gsutil_api, logger, test_method=None):
  """Downloads an object to a local file.

  Args:
    src_url: Source CloudUrl.
    src_obj_metadata: Metadata from the source object.
    dst_url: Destination FileUrl.
    gsutil_api: gsutil Cloud API instance to use for the download.
    logger: for outputting log messages.
    test_method: Optional test method for modifying the file before validation
                 during unit tests.
  Returns:
    (elapsed_time, bytes_transferred, dst_url, md5), excluding overhead like
    initial GET.

  Raises:
    CommandException: if errors encountered.
  """
  global open_files_map
  file_name = dst_url.object_name
  dir_name = os.path.dirname(file_name)
  if dir_name and not os.path.exists(dir_name):
    # Do dir creation in try block so can ignore case where dir already
    # exists. This is needed to avoid a race condition when running gsutil
    # -m cp.
    try:
      os.makedirs(dir_name)
    except OSError, e:
      if e.errno != errno.EEXIST:
        raise
  api_selector = gsutil_api.GetApiSelector(provider=src_url.scheme)
  # For gzipped objects download to a temp file and unzip. For the XML API,
  # the represents the result of a HEAD request. For the JSON API, this is
  # the stored encoding which the service may not respect. However, if the
  # server sends decompressed bytes for a file that is stored compressed
  # (double compressed case), there is no way we can validate the hash and
  # we will fail our hash check for the object.
  if (src_obj_metadata.contentEncoding and
      src_obj_metadata.contentEncoding.lower().endswith('gzip')):
    # We can't use tempfile.mkstemp() here because we need a predictable
    # filename for resumable downloads.
    download_file_name = _GetDownloadZipFileName(file_name)
    logger.info(
        'Downloading to temp gzip filename %s', download_file_name)
    need_to_unzip = True
  else:
    download_file_name = file_name
    need_to_unzip = False

  if download_file_name.endswith(dst_url.delim):
    logger.warn('\n'.join(textwrap.wrap(
        'Skipping attempt to download to filename ending with slash (%s). This '
        'typically happens when using gsutil to download from a subdirectory '
        'created by the Cloud Console (https://cloud.google.com/console)'
        % download_file_name)))
    return (0, 0, dst_url, '')

  # Set up hash digesters.
  hash_algs = GetDownloadHashAlgs(
      logger, src_has_md5=src_obj_metadata.md5Hash,
      src_has_crc32c=src_obj_metadata.crc32c)
  digesters = dict((alg, hash_algs[alg]()) for alg in hash_algs or {})

  fp = None
  # Tracks whether the server used a gzip encoding.
  server_encoding = None
  download_complete = False
  download_strategy = _SelectDownloadStrategy(dst_url)
  download_start_point = 0
  # This is used for resuming downloads, but also for passing the mediaLink
  # and size into the download for new downloads so that we can avoid
  # making an extra HTTP call.
  serialization_data = None
  serialization_dict = GetDownloadSerializationDict(src_obj_metadata)
  open_files = []
  try:
    if download_strategy is CloudApi.DownloadStrategy.ONE_SHOT:
      fp = open(download_file_name, 'wb')
    elif download_strategy is CloudApi.DownloadStrategy.RESUMABLE:
      # If this is a resumable download, we need to open the file for append and
      # manage a tracker file.
      if open_files_map.get(download_file_name, False):
        # Ensure another process/thread is not already writing to this file.
        raise FileConcurrencySkipError
      open_files.append(download_file_name)
      open_files_map[download_file_name] = True
      fp = open(download_file_name, 'ab')

      resuming = ReadOrCreateDownloadTrackerFile(
          src_obj_metadata, dst_url, api_selector)
      if resuming:
        # Find out how far along we are so we can request the appropriate
        # remaining range of the object.
        existing_file_size = GetFileSize(fp, position_to_eof=True)
        if existing_file_size > src_obj_metadata.size:
          DeleteTrackerFile(GetTrackerFilePath(
              dst_url, TrackerFileType.DOWNLOAD, api_selector))
          raise CommandException(
              '%s is larger (%d) than %s (%d).\nDeleting tracker file, so '
              'if you re-try this download it will start from scratch' %
              (download_file_name, existing_file_size, src_url.object_name,
               src_obj_metadata.size))
        else:
          if existing_file_size == src_obj_metadata.size:
            logger.info(
                'Download already complete for file %s, skipping download but '
                'will run integrity checks.', download_file_name)
            download_complete = True
          else:
            download_start_point = existing_file_size
            serialization_dict['progress'] = download_start_point
            logger.info('Resuming download for %s', src_url.url_string)
          # Catch up our digester with the hash data.
          if existing_file_size > TEN_MIB:
            for alg_name in digesters:
              logger.info(
                  'Catching up %s for %s', alg_name, download_file_name)
          with open(download_file_name, 'rb') as hash_fp:
            while True:
              data = hash_fp.read(DEFAULT_FILE_BUFFER_SIZE)
              if not data:
                break
              for alg_name in digesters:
                digesters[alg_name].update(data)
      else:
        # Starting a new download, blow away whatever is already there.
        fp.truncate(0)
        fp.seek(0)

    else:
      raise CommandException('Invalid download strategy %s chosen for'
                             'file %s' % (download_strategy, fp.name))

    if not dst_url.IsStream():
      serialization_data = json.dumps(serialization_dict)

    progress_callback = FileProgressCallbackHandler(
        ConstructAnnounceText('Downloading', dst_url.url_string),
        logger).call
    if global_copy_helper_opts.test_callback_file:
      with open(global_copy_helper_opts.test_callback_file, 'rb') as test_fp:
        progress_callback = pickle.loads(test_fp.read()).call

    start_time = time.time()
    # TODO: With gzip encoding (which may occur on-the-fly and not be part of
    # the object's metadata), when we request a range to resume, it's possible
    # that the server will just resend the entire object, which means our
    # caught-up hash will be incorrect.  We recalculate the hash on
    # the local file in the case of a failed gzip hash anyway, but it would
    # be better if we actively detected this case.
    if not download_complete:
      server_encoding = gsutil_api.GetObjectMedia(
          src_url.bucket_name, src_url.object_name, fp,
          start_byte=download_start_point, generation=src_url.generation,
          object_size=src_obj_metadata.size,
          download_strategy=download_strategy, provider=src_url.scheme,
          serialization_data=serialization_data, digesters=digesters,
          progress_callback=progress_callback)

    end_time = time.time()

    # If a custom test method is defined, call it here. For the copy command,
    # test methods are expected to take one argument: an open file pointer,
    # and are used to perturb the open file during download to exercise
    # download error detection.
    if test_method:
      test_method(fp)

  except ResumableDownloadException as e:
    logger.warning('Caught ResumableDownloadException (%s) for file %s.',
                   e.reason, file_name)
    raise

  finally:
    if fp:
      fp.close()
    for file_name in open_files:
      open_files_map.delete(file_name)

  # If we decompressed a content-encoding gzip file on the fly, this may not
  # be accurate, but it is the best we can do without going deep into the
  # underlying HTTP libraries. Note that this value is only used for
  # reporting in log messages; inaccuracy doesn't impact the integrity of the
  # download.
  bytes_transferred = src_obj_metadata.size - download_start_point
  server_gzip = server_encoding and server_encoding.lower().endswith('gzip')
  local_md5 = _ValidateDownloadHashes(logger, src_url, src_obj_metadata,
                                      dst_url, need_to_unzip, server_gzip,
                                      digesters, hash_algs, api_selector,
                                      bytes_transferred)

  return (end_time - start_time, bytes_transferred, dst_url, local_md5)


def _GetDownloadZipFileName(file_name):
  """Returns the file name for a temporarily compressed downloaded file."""
  return '%s_.gztmp' % file_name


def _ValidateDownloadHashes(logger, src_url, src_obj_metadata, dst_url,
                            need_to_unzip, server_gzip, digesters, hash_algs,
                            api_selector, bytes_transferred):
  """Validates a downloaded file's integrity.

  Args:
    logger: For outputting log messages.
    src_url: StorageUrl for the source object.
    src_obj_metadata: Metadata for the source object, potentially containing
                      hash values.
    dst_url: StorageUrl describing the destination file.
    need_to_unzip: If true, a temporary zip file was used and must be
                   uncompressed as part of validation.
    server_gzip: If true, the server gzipped the bytes (regardless of whether
                 the object metadata claimed it was gzipped).
    digesters: dict of {string, hash digester} that contains up-to-date digests
               computed during the download. If a digester for a particular
               algorithm is None, an up-to-date digest is not available and the
               hash must be recomputed from the local file.
    hash_algs: dict of {string, hash algorithm} that can be used if digesters
               don't have up-to-date digests.
    api_selector: The Cloud API implementation used (used tracker file naming).
    bytes_transferred: Number of bytes downloaded (used for logging).

  Returns:
    An MD5 of the local file, if one was calculated as part of the integrity
    check.
  """
  file_name = dst_url.object_name
  download_file_name = (_GetDownloadZipFileName(file_name) if need_to_unzip else
                        file_name)
  digesters_succeeded = True
  for alg in digesters:
    # If we get a digester with a None algorithm, the underlying
    # implementation failed to calculate a digest, so we will need to
    # calculate one from scratch.
    if not digesters[alg]:
      digesters_succeeded = False
      break

  if digesters_succeeded:
    local_hashes = _CreateDigestsFromDigesters(digesters)
  else:
    local_hashes = _CreateDigestsFromLocalFile(
        logger, hash_algs, download_file_name, src_obj_metadata)

  digest_verified = True
  hash_invalid_exception = None
  try:
    _CheckHashes(logger, src_url, src_obj_metadata, download_file_name,
                 local_hashes)
    DeleteTrackerFile(GetTrackerFilePath(
        dst_url, TrackerFileType.DOWNLOAD, api_selector))
  except HashMismatchException, e:
    # If an non-gzipped object gets sent with gzip content encoding, the hash
    # we calculate will match the gzipped bytes, not the original object. Thus,
    # we'll need to calculate and check it after unzipping.
    if server_gzip:
      logger.debug(
          'Hash did not match but server gzipped the content, will '
          'recalculate.')
      digest_verified = False
    elif api_selector == ApiSelector.XML:
      logger.debug(
          'Hash did not match but server may have gzipped the content, will '
          'recalculate.')
      # Save off the exception in case this isn't a gzipped file.
      hash_invalid_exception = e
      digest_verified = False
    else:
      DeleteTrackerFile(GetTrackerFilePath(
          dst_url, TrackerFileType.DOWNLOAD, api_selector))
      if _RENAME_ON_HASH_MISMATCH:
        os.rename(download_file_name,
                  download_file_name + _RENAME_ON_HASH_MISMATCH_SUFFIX)
      else:
        os.unlink(download_file_name)
      raise

  if server_gzip and not need_to_unzip:
    # Server compressed bytes on-the-fly, thus we need to rename and decompress.
    # We can't decompress on-the-fly because prior to Python 3.2 the gzip
    # module makes a bunch of seek calls on the stream.
    download_file_name = _GetDownloadZipFileName(file_name)
    os.rename(file_name, download_file_name)

  if need_to_unzip or server_gzip:
    # Log that we're uncompressing if the file is big enough that
    # decompressing would make it look like the transfer "stalled" at the end.
    if bytes_transferred > TEN_MIB:
      logger.info(
          'Uncompressing downloaded tmp file to %s...', file_name)

    # Downloaded gzipped file to a filename w/o .gz extension, so unzip.
    gzip_fp = None
    try:
      gzip_fp = gzip.open(download_file_name, 'rb')
      with open(file_name, 'wb') as f_out:
        data = gzip_fp.read(GZIP_CHUNK_SIZE)
        while data:
          f_out.write(data)
          data = gzip_fp.read(GZIP_CHUNK_SIZE)
    except IOError, e:
      # In the XML case where we don't know if the file was gzipped, raise
      # the original hash exception if we find that it wasn't.
      if 'Not a gzipped file' in str(e) and hash_invalid_exception:
        # Linter improperly thinks we're raising None despite the above check.
        # pylint: disable=raising-bad-type
        raise hash_invalid_exception
    finally:
      if gzip_fp:
        gzip_fp.close()

    os.unlink(download_file_name)

  if not digest_verified:
    try:
      # Recalculate hashes on the unzipped local file.
      local_hashes = _CreateDigestsFromLocalFile(logger, hash_algs, file_name,
                                                 src_obj_metadata)
      _CheckHashes(logger, src_url, src_obj_metadata, file_name, local_hashes)
      DeleteTrackerFile(GetTrackerFilePath(
          dst_url, TrackerFileType.DOWNLOAD, api_selector))
    except HashMismatchException:
      DeleteTrackerFile(GetTrackerFilePath(
          dst_url, TrackerFileType.DOWNLOAD, api_selector))
      if _RENAME_ON_HASH_MISMATCH:
        os.rename(file_name,
                  file_name + _RENAME_ON_HASH_MISMATCH_SUFFIX)
      else:
        os.unlink(file_name)
      raise

  if 'md5' in local_hashes:
    return local_hashes['md5']


def _CopyFileToFile(src_url, dst_url):
  """Copies a local file to a local file.

  Args:
    src_url: Source FileUrl.
    dst_url: Destination FileUrl.
  Returns:
    (elapsed_time, bytes_transferred, dst_url, md5=None).

  Raises:
    CommandException: if errors encountered.
  """
  src_fp = GetStreamFromFileUrl(src_url)
  dir_name = os.path.dirname(dst_url.object_name)
  if dir_name and not os.path.exists(dir_name):
    os.makedirs(dir_name)
  dst_fp = open(dst_url.object_name, 'wb')
  start_time = time.time()
  shutil.copyfileobj(src_fp, dst_fp)
  end_time = time.time()
  return (end_time - start_time, os.path.getsize(dst_url.object_name),
          dst_url, None)


def _DummyTrackerCallback(_):
  pass


# pylint: disable=undefined-variable
def _CopyObjToObjDaisyChainMode(src_url, src_obj_metadata, dst_url,
                                dst_obj_metadata, preconditions, gsutil_api,
                                logger):
  """Copies from src_url to dst_url in "daisy chain" mode.

  See -D OPTION documentation about what daisy chain mode is.

  Args:
    src_url: Source CloudUrl
    src_obj_metadata: Metadata from source object
    dst_url: Destination CloudUrl
    dst_obj_metadata: Object-specific metadata that should be overidden during
                      the copy.
    preconditions: Preconditions to use for the copy.
    gsutil_api: gsutil Cloud API to use for the copy.
    logger: For outputting log messages.

  Returns:
    (elapsed_time, bytes_transferred, dst_url with generation,
    md5 hash of destination) excluding overhead like initial GET.

  Raises:
    CommandException: if errors encountered.
  """
  # We don't attempt to preserve ACLs across providers because
  # GCS and S3 support different ACLs and disjoint principals.
  if (global_copy_helper_opts.preserve_acl
      and src_url.scheme != dst_url.scheme):
    raise NotImplementedError(
        'Cross-provider cp -p not supported')
  if not global_copy_helper_opts.preserve_acl:
    dst_obj_metadata.acl = []

  # Don't use callbacks for downloads on the daisy chain wrapper because
  # upload callbacks will output progress, but respect test hooks if present.
  progress_callback = None
  if global_copy_helper_opts.test_callback_file:
    with open(global_copy_helper_opts.test_callback_file, 'rb') as test_fp:
      progress_callback = pickle.loads(test_fp.read()).call

  start_time = time.time()
  upload_fp = DaisyChainWrapper(src_url, src_obj_metadata.size, gsutil_api,
                                progress_callback=progress_callback)
  uploaded_object = None
  if src_obj_metadata.size == 0:
    # Resumable uploads of size 0 are not supported.
    uploaded_object = gsutil_api.UploadObject(
        upload_fp, object_metadata=dst_obj_metadata,
        canned_acl=global_copy_helper_opts.canned_acl,
        preconditions=preconditions, provider=dst_url.scheme,
        fields=UPLOAD_RETURN_FIELDS, size=src_obj_metadata.size)
  else:
    # TODO: Support process-break resumes. This will resume across connection
    # breaks and server errors, but the tracker callback is a no-op so this
    # won't resume across gsutil runs.
    # TODO: Test retries via test_callback_file.
    uploaded_object = gsutil_api.UploadObjectResumable(
        upload_fp, object_metadata=dst_obj_metadata,
        canned_acl=global_copy_helper_opts.canned_acl,
        preconditions=preconditions, provider=dst_url.scheme,
        fields=UPLOAD_RETURN_FIELDS, size=src_obj_metadata.size,
        progress_callback=FileProgressCallbackHandler(
            ConstructAnnounceText('Uploading', dst_url.url_string),
            logger).call,
        tracker_callback=_DummyTrackerCallback)
  end_time = time.time()

  try:
    _CheckCloudHashes(logger, src_url, dst_url, src_obj_metadata,
                      uploaded_object)
  except HashMismatchException:
    if _RENAME_ON_HASH_MISMATCH:
      corrupted_obj_metadata = apitools_messages.Object(
          name=dst_obj_metadata.name,
          bucket=dst_obj_metadata.bucket,
          etag=uploaded_object.etag)
      dst_obj_metadata.name = (dst_url.object_name +
                               _RENAME_ON_HASH_MISMATCH_SUFFIX)
      gsutil_api.CopyObject(corrupted_obj_metadata,
                            dst_obj_metadata, provider=dst_url.scheme)
    # If the digest doesn't match, delete the object.
    gsutil_api.DeleteObject(dst_url.bucket_name, dst_url.object_name,
                            generation=uploaded_object.generation,
                            provider=dst_url.scheme)
    raise

  result_url = dst_url.Clone()
  result_url.generation = GenerationFromUrlAndString(
      result_url, uploaded_object.generation)

  return (end_time - start_time, src_obj_metadata.size, result_url,
          uploaded_object.md5Hash)


# pylint: disable=undefined-variable
# pylint: disable=too-many-statements
def PerformCopy(logger, src_url, dst_url, gsutil_api, command_obj,
                copy_exception_handler, allow_splitting=True,
                headers=None, manifest=None, gzip_exts=None, test_method=None):
  """Performs copy from src_url to dst_url, handling various special cases.

  Args:
    logger: for outputting log messages.
    src_url: Source StorageUrl.
    dst_url: Destination StorageUrl.
    gsutil_api: gsutil Cloud API instance to use for the copy.
    command_obj: command object for use in Apply in parallel composite uploads.
    copy_exception_handler: for handling copy exceptions during Apply.
    allow_splitting: Whether to allow the file to be split into component
                     pieces for an parallel composite upload.
    headers: optional headers to use for the copy operation.
    manifest: optional manifest for tracking copy operations.
    gzip_exts: List of file extensions to gzip for uploads, if any.
    test_method: optional test method for modifying files during unit tests.

  Returns:
    (elapsed_time, bytes_transferred, version-specific dst_url) excluding
    overhead like initial GET.

  Raises:
    ItemExistsError: if no clobber flag is specified and the destination
        object already exists.
    SkipUnsupportedObjectError: if skip_unsupported_objects flag is specified
        and the source is an unsupported type.
    CommandException: if other errors encountered.
  """
  if headers:
    dst_obj_headers = headers.copy()
  else:
    dst_obj_headers = {}

  # Create a metadata instance for each destination object so metadata
  # such as content-type can be applied per-object.
  # Initialize metadata from any headers passed in via -h.
  dst_obj_metadata = ObjectMetadataFromHeaders(dst_obj_headers)

  if dst_url.IsCloudUrl() and dst_url.scheme == 'gs':
    preconditions = PreconditionsFromHeaders(dst_obj_headers)
  else:
    preconditions = Preconditions()

  src_obj_metadata = None
  src_obj_filestream = None
  if src_url.IsCloudUrl():
    src_obj_fields = None
    if dst_url.IsCloudUrl():
      # For cloud or daisy chain copy, we need every copyable field.
      # If we're not modifying or overriding any of the fields, we can get
      # away without retrieving the object metadata because the copy
      # operation can succeed with just the destination bucket and object
      # name.  But if we are sending any metadata, the JSON API will expect a
      # complete object resource.  Since we want metadata like the object size
      # for our own tracking, we just get all of the metadata here.
      src_obj_fields = ['cacheControl', 'componentCount',
                        'contentDisposition', 'contentEncoding',
                        'contentLanguage', 'contentType', 'crc32c',
                        'etag', 'generation', 'md5Hash', 'mediaLink',
                        'metadata', 'metageneration', 'size']
      # We only need the ACL if we're going to preserve it.
      if global_copy_helper_opts.preserve_acl:
        src_obj_fields.append('acl')
      if (src_url.scheme == dst_url.scheme
          and not global_copy_helper_opts.daisy_chain):
        copy_in_the_cloud = True
      else:
        copy_in_the_cloud = False
    else:
      # Just get the fields needed to validate the download.
      src_obj_fields = ['crc32c', 'contentEncoding', 'contentType', 'etag',
                        'mediaLink', 'md5Hash', 'size']

    if (src_url.scheme == 's3' and
        global_copy_helper_opts.skip_unsupported_objects):
      src_obj_fields.append('storageClass')

    try:
      src_generation = GenerationFromUrlAndString(src_url, src_url.generation)
      src_obj_metadata = gsutil_api.GetObjectMetadata(
          src_url.bucket_name, src_url.object_name,
          generation=src_generation, provider=src_url.scheme,
          fields=src_obj_fields)
    except NotFoundException:
      raise CommandException(
          'NotFoundException: Could not retrieve source object %s.' %
          src_url.url_string)
    if (src_url.scheme == 's3' and
        global_copy_helper_opts.skip_unsupported_objects and
        src_obj_metadata.storageClass == 'GLACIER'):
      raise SkipGlacierError()

    src_obj_size = src_obj_metadata.size
    dst_obj_metadata.contentType = src_obj_metadata.contentType
    if global_copy_helper_opts.preserve_acl:
      dst_obj_metadata.acl = src_obj_metadata.acl
      # Special case for S3-to-S3 copy URLs using
      # global_copy_helper_opts.preserve_acl.
      # dst_url will be verified in _CopyObjToObjDaisyChainMode if it
      # is not s3 (and thus differs from src_url).
      if src_url.scheme == 's3':
        acl_text = S3MarkerAclFromObjectMetadata(src_obj_metadata)
        if acl_text:
          AddS3MarkerAclToObjectMetadata(dst_obj_metadata, acl_text)
  else:
    try:
      src_obj_filestream = GetStreamFromFileUrl(src_url)
    except Exception, e:  # pylint: disable=broad-except
      raise CommandException('Error opening file "%s": %s.' % (src_url,
                                                               e.message))
    if src_url.IsStream():
      src_obj_size = None
    else:
      src_obj_size = os.path.getsize(src_url.object_name)

  if global_copy_helper_opts.use_manifest:
    # Set the source size in the manifest.
    manifest.Set(src_url.url_string, 'size', src_obj_size)

  if (dst_url.scheme == 's3' and src_obj_size > S3_MAX_UPLOAD_SIZE
      and src_url != 's3'):
    raise CommandException(
        '"%s" exceeds the maximum gsutil-supported size for an S3 upload. S3 '
        'objects greater than %s in size require multipart uploads, which '
        'gsutil does not support.' % (src_url,
                                      MakeHumanReadable(S3_MAX_UPLOAD_SIZE)))

  # On Windows, stdin is opened as text mode instead of binary which causes
  # problems when piping a binary file, so this switches it to binary mode.
  if IS_WINDOWS and src_url.IsFileUrl() and src_url.IsStream():
    msvcrt.setmode(GetStreamFromFileUrl(src_url).fileno(), os.O_BINARY)

  if global_copy_helper_opts.no_clobber:
    # There are two checks to prevent clobbering:
    # 1) The first check is to see if the URL
    #    already exists at the destination and prevent the upload/download
    #    from happening. This is done by the exists() call.
    # 2) The second check is only relevant if we are writing to gs. We can
    #    enforce that the server only writes the object if it doesn't exist
    #    by specifying the header below. This check only happens at the
    #    server after the complete file has been uploaded. We specify this
    #    header to prevent a race condition where a destination file may
    #    be created after the first check and before the file is fully
    #    uploaded.
    # In order to save on unnecessary uploads/downloads we perform both
    # checks. However, this may come at the cost of additional HTTP calls.
    if preconditions.gen_match:
      raise ArgumentException('Specifying x-goog-if-generation-match is '
                              'not supported with cp -n')
    else:
      preconditions.gen_match = 0
    if dst_url.IsFileUrl() and os.path.exists(dst_url.object_name):
      # The local file may be a partial. Check the file sizes.
      if src_obj_size == os.path.getsize(dst_url.object_name):
        raise ItemExistsError()
    elif dst_url.IsCloudUrl():
      try:
        dst_object = gsutil_api.GetObjectMetadata(
            dst_url.bucket_name, dst_url.object_name, provider=dst_url.scheme)
      except NotFoundException:
        dst_object = None
      if dst_object:
        raise ItemExistsError()

  if dst_url.IsCloudUrl():
    # Cloud storage API gets object and bucket name from metadata.
    dst_obj_metadata.name = dst_url.object_name
    dst_obj_metadata.bucket = dst_url.bucket_name
    if src_url.IsCloudUrl():
      # Preserve relevant metadata from the source object if it's not already
      # provided from the headers.
      CopyObjectMetadata(src_obj_metadata, dst_obj_metadata, override=False)
      src_obj_metadata.name = src_url.object_name
      src_obj_metadata.bucket = src_url.bucket_name
    else:
      _SetContentTypeFromFile(src_url, dst_obj_metadata)
  else:
    # Files don't have Cloud API metadata.
    dst_obj_metadata = None

  _LogCopyOperation(logger, src_url, dst_url, dst_obj_metadata)

  if src_url.IsCloudUrl():
    if dst_url.IsFileUrl():
      return _DownloadObjectToFile(src_url, src_obj_metadata, dst_url,
                                   gsutil_api, logger, test_method=test_method)
    elif copy_in_the_cloud:
      return _CopyObjToObjInTheCloud(src_url, src_obj_metadata, dst_url,
                                     dst_obj_metadata, preconditions,
                                     gsutil_api, logger)
    else:
      return _CopyObjToObjDaisyChainMode(src_url, src_obj_metadata,
                                         dst_url, dst_obj_metadata,
                                         preconditions, gsutil_api, logger)
  else:  # src_url.IsFileUrl()
    if dst_url.IsCloudUrl():
      return _UploadFileToObject(
          src_url, src_obj_filestream, src_obj_size, dst_url,
          dst_obj_metadata, preconditions, gsutil_api, logger, command_obj,
          copy_exception_handler, gzip_exts=gzip_exts,
          allow_splitting=allow_splitting)
    else:  # dst_url.IsFileUrl()
      return _CopyFileToFile(src_url, dst_url)


class Manifest(object):
  """Stores the manifest items for the CpCommand class."""

  def __init__(self, path):
    # self.items contains a dictionary of rows
    self.items = {}
    self.manifest_filter = {}
    self.lock = CreateLock()

    self.manifest_path = os.path.expanduser(path)
    self._ParseManifest()
    self._CreateManifestFile()

  def _ParseManifest(self):
    """Load and parse a manifest file.

    This information will be used to skip any files that have a skip or OK
    status.
    """
    try:
      if os.path.exists(self.manifest_path):
        with open(self.manifest_path, 'rb') as f:
          first_row = True
          reader = csv.reader(f)
          for row in reader:
            if first_row:
              try:
                source_index = row.index('Source')
                result_index = row.index('Result')
              except ValueError:
                # No header and thus not a valid manifest file.
                raise CommandException(
                    'Missing headers in manifest file: %s' % self.manifest_path)
            first_row = False
            source = row[source_index]
            result = row[result_index]
            if result in ['OK', 'skip']:
              # We're always guaranteed to take the last result of a specific
              # source url.
              self.manifest_filter[source] = result
    except IOError:
      raise CommandException('Could not parse %s' % self.manifest_path)

  def WasSuccessful(self, src):
    """Returns whether the specified src url was marked as successful."""
    return src in self.manifest_filter

  def _CreateManifestFile(self):
    """Opens the manifest file and assigns it to the file pointer."""
    try:
      if ((not os.path.exists(self.manifest_path))
          or (os.stat(self.manifest_path).st_size == 0)):
        # Add headers to the new file.
        with open(self.manifest_path, 'wb', 1) as f:
          writer = csv.writer(f)
          writer.writerow(['Source',
                           'Destination',
                           'Start',
                           'End',
                           'Md5',
                           'UploadId',
                           'Source Size',
                           'Bytes Transferred',
                           'Result',
                           'Description'])
    except IOError:
      raise CommandException('Could not create manifest file.')

  def Set(self, url, key, value):
    if value is None:
      # In case we don't have any information to set we bail out here.
      # This is so that we don't clobber existing information.
      # To zero information pass '' instead of None.
      return
    if url in self.items:
      self.items[url][key] = value
    else:
      self.items[url] = {key: value}

  def Initialize(self, source_url, destination_url):
    # Always use the source_url as the key for the item. This is unique.
    self.Set(source_url, 'source_uri', source_url)
    self.Set(source_url, 'destination_uri', destination_url)
    self.Set(source_url, 'start_time', datetime.datetime.utcnow())

  def SetResult(self, source_url, bytes_transferred, result,
                description=''):
    self.Set(source_url, 'bytes', bytes_transferred)
    self.Set(source_url, 'result', result)
    self.Set(source_url, 'description', description)
    self.Set(source_url, 'end_time', datetime.datetime.utcnow())
    self._WriteRowToManifestFile(source_url)
    self._RemoveItemFromManifest(source_url)

  def _WriteRowToManifestFile(self, url):
    """Writes a manifest entry to the manifest file for the url argument."""
    row_item = self.items[url]
    data = [
        str(row_item['source_uri'].encode(UTF8)),
        str(row_item['destination_uri'].encode(UTF8)),
        '%sZ' % row_item['start_time'].isoformat(),
        '%sZ' % row_item['end_time'].isoformat(),
        row_item['md5'] if 'md5' in row_item else '',
        row_item['upload_id'] if 'upload_id' in row_item else '',
        str(row_item['size']) if 'size' in row_item else '',
        str(row_item['bytes']) if 'bytes' in row_item else '',
        row_item['result'],
        row_item['description'].encode(UTF8)]

    # Aquire a lock to prevent multiple threads writing to the same file at
    # the same time. This would cause a garbled mess in the manifest file.
    with self.lock:
      with open(self.manifest_path, 'a', 1) as f:  # 1 == line buffered
        writer = csv.writer(f)
        writer.writerow(data)

  def _RemoveItemFromManifest(self, url):
    # Remove the item from the dictionary since we're done with it and
    # we don't want the dictionary to grow too large in memory for no good
    # reason.
    del self.items[url]


class ItemExistsError(Exception):
  """Exception class for objects that are skipped because they already exist."""
  pass


class SkipUnsupportedObjectError(Exception):
  """Exception for objects skipped because they are an unsupported type."""

  def __init__(self):
    super(SkipUnsupportedObjectError, self).__init__()
    self.unsupported_type = 'Unknown'


class SkipGlacierError(SkipUnsupportedObjectError):
  """Exception for objects skipped because they are an unsupported type."""

  def __init__(self):
    super(SkipGlacierError, self).__init__()
    self.unsupported_type = 'GLACIER'


def GetPathBeforeFinalDir(url):
  """Returns the path section before the final directory component of the URL.

  This handles cases for file system directories, bucket, and bucket
  subdirectories. Example: for gs://bucket/dir/ we'll return 'gs://bucket',
  and for file://dir we'll return file://

  Args:
    url: StorageUrl representing a filesystem directory, cloud bucket or
         bucket subdir.

  Returns:
    String name of above-described path, sans final path separator.
  """
  sep = url.delim
  if url.IsFileUrl():
    past_scheme = url.url_string[len('file://'):]
    if past_scheme.find(sep) == -1:
      return 'file://'
    else:
      return 'file://%s' % past_scheme.rstrip(sep).rpartition(sep)[0]
  if url.IsBucket():
    return '%s://' % url.scheme
  # Else it names a bucket subdir.
  return url.url_string.rstrip(sep).rpartition(sep)[0]


def _DivideAndCeil(dividend, divisor):
  """Returns ceil(dividend / divisor).

  Takes care to avoid the pitfalls of floating point arithmetic that could
  otherwise yield the wrong result for large numbers.

  Args:
    dividend: Dividend for the operation.
    divisor: Divisor for the operation.

  Returns:
    Quotient.
  """
  quotient = dividend // divisor
  if (dividend % divisor) != 0:
    quotient += 1
  return quotient


def _GetPartitionInfo(file_size, max_components, default_component_size):
  """Gets info about a file partition for parallel composite uploads.

  Args:
    file_size: The number of bytes in the file to be partitioned.
    max_components: The maximum number of components that can be composed.
    default_component_size: The size of a component, assuming that
                            max_components is infinite.
  Returns:
    The number of components in the partitioned file, and the size of each
    component (except the last, which will have a different size iff
    file_size != 0 (mod num_components)).
  """
  # num_components = ceil(file_size / default_component_size)
  num_components = _DivideAndCeil(file_size, default_component_size)

  # num_components must be in the range [2, max_components]
  num_components = max(min(num_components, max_components), 2)

  # component_size = ceil(file_size / num_components)
  component_size = _DivideAndCeil(file_size, num_components)
  return (num_components, component_size)


def _DeleteObjectFn(cls, url_to_delete, thread_state=None):
  """Wrapper function to be used with command.Apply()."""
  gsutil_api = GetCloudApiInstance(cls, thread_state)
  gsutil_api.DeleteObject(
      url_to_delete.bucket_name, url_to_delete.object_name,
      generation=url_to_delete.generation, provider=url_to_delete.scheme)


def _ParseParallelUploadTrackerFile(tracker_file, tracker_file_lock):
  """Parse the tracker file from the last parallel composite upload attempt.

  If it exists, the tracker file is of the format described in
  _CreateParallelUploadTrackerFile. If the file doesn't exist or cannot be
  read, then the upload will start from the beginning.

  Args:
    tracker_file: The name of the file to parse.
    tracker_file_lock: Lock protecting access to the tracker file.

  Returns:
    random_prefix: A randomly-generated prefix to the name of the
                   temporary components.
    existing_objects: A list of ObjectFromTracker objects representing
                      the set of files that have already been uploaded.
  """

  def GenerateRandomPrefix():
    return str(random.randint(1, (10 ** 10) - 1))

  existing_objects = []
  try:
    with tracker_file_lock:
      with open(tracker_file, 'r') as fp:
        lines = fp.readlines()
        lines = [line.strip() for line in lines]
        if not lines:
          print('Parallel upload tracker file (%s) was invalid. '
                'Restarting upload from scratch.' % tracker_file)
          lines = [GenerateRandomPrefix()]

  except IOError as e:
    # We can't read the tracker file, so generate a new random prefix.
    lines = [GenerateRandomPrefix()]

    # Ignore non-existent file (happens first time an upload
    # is attempted on a file), but warn user for other errors.
    if e.errno != errno.ENOENT:
      # Will restart because we failed to read in the file.
      print('Couldn\'t read parallel upload tracker file (%s): %s. '
            'Restarting upload from scratch.' % (tracker_file, e.strerror))

  # The first line contains the randomly-generated prefix.
  random_prefix = lines[0]

  # The remaining lines were written in pairs to describe a single component
  # in the form:
  #   object_name (without random prefix)
  #   generation
  # Newlines are used as the delimiter because only newlines and carriage
  # returns are invalid characters in object names, and users can specify
  # a custom prefix in the config file.
  i = 1
  while i < len(lines):
    (name, generation) = (lines[i], lines[i+1])
    if not generation:
      # Cover the '' case.
      generation = None
    existing_objects.append(ObjectFromTracker(name, generation))
    i += 2
  return (random_prefix, existing_objects)


def _AppendComponentTrackerToParallelUploadTrackerFile(tracker_file, component,
                                                       tracker_file_lock):
  """Appends info about the uploaded component to an existing tracker file.

  Follows the format described in _CreateParallelUploadTrackerFile.

  Args:
    tracker_file: Tracker file to append to.
    component: Component that was uploaded.
    tracker_file_lock: Thread and process-safe Lock for the tracker file.
  """
  lines = _GetParallelUploadTrackerFileLinesForComponents([component])
  lines = [line + '\n' for line in lines]
  with tracker_file_lock:
    with open(tracker_file, 'a') as f:
      f.writelines(lines)


def _CreateParallelUploadTrackerFile(tracker_file, random_prefix, components,
                                     tracker_file_lock):
  """Writes information about components that were successfully uploaded.

  This way the upload can be resumed at a later date. The tracker file has
  the format:
    random_prefix
    temp_object_1_name
    temp_object_1_generation
    .
    .
    .
    temp_object_N_name
    temp_object_N_generation
    where N is the number of components that have been successfully uploaded.

  Args:
    tracker_file: The name of the parallel upload tracker file.
    random_prefix: The randomly-generated prefix that was used for
                   for uploading any existing components.
    components: A list of ObjectFromTracker objects that were uploaded.
    tracker_file_lock: The lock protecting access to the tracker file.
  """
  lines = [random_prefix]
  lines += _GetParallelUploadTrackerFileLinesForComponents(components)
  lines = [line + '\n' for line in lines]
  try:
    with tracker_file_lock:
      open(tracker_file, 'w').close()  # Clear the file.
      with open(tracker_file, 'w') as f:
        f.writelines(lines)
  except IOError as e:
    RaiseUnwritableTrackerFileException(tracker_file, e.strerror)


def _GetParallelUploadTrackerFileLinesForComponents(components):
  """Return a list of the lines for use in a parallel upload tracker file.

  The lines represent the given components, using the format as described in
  _CreateParallelUploadTrackerFile.

  Args:
    components: A list of ObjectFromTracker objects that were uploaded.

  Returns:
    Lines describing components with their generation for outputting to the
    tracker file.
  """
  lines = []
  for component in components:
    generation = None
    generation = component.generation
    if not generation:
      generation = ''
    lines += [component.object_name, str(generation)]
  return lines


def FilterExistingComponents(dst_args, existing_components, bucket_url,
                             gsutil_api):
  """Determines course of action for component objects.

  Given the list of all target objects based on partitioning the file and
  the list of objects that have already been uploaded successfully,
  this function determines which objects should be uploaded, which
  existing components are still valid, and which existing components should
  be deleted.

  Args:
    dst_args: The map of file_name -> PerformParallelUploadFileToObjectArgs
              calculated by partitioning the file.
    existing_components: A list of ObjectFromTracker objects that have been
                         uploaded in the past.
    bucket_url: CloudUrl of the bucket in which the components exist.
    gsutil_api: gsutil Cloud API instance to use for retrieving object metadata.

  Returns:
    components_to_upload: List of components that need to be uploaded.
    uploaded_components: List of components that have already been
                         uploaded and are still valid.
    existing_objects_to_delete: List of components that have already
                                been uploaded, but are no longer valid
                                and are in a versioned bucket, and
                                therefore should be deleted.
  """
  components_to_upload = []
  existing_component_names = [component.object_name
                              for component in existing_components]
  for component_name in dst_args:
    if component_name not in existing_component_names:
      components_to_upload.append(dst_args[component_name])

  objects_already_chosen = []

  # Don't reuse any temporary components whose MD5 doesn't match the current
  # MD5 of the corresponding part of the file. If the bucket is versioned,
  # also make sure that we delete the existing temporary version.
  existing_objects_to_delete = []
  uploaded_components = []
  for tracker_object in existing_components:
    if (tracker_object.object_name not in dst_args.keys()
        or tracker_object.object_name in objects_already_chosen):
      # This could happen if the component size has changed. This also serves
      # to handle object names that get duplicated in the tracker file due
      # to people doing things they shouldn't (e.g., overwriting an existing
      # temporary component in a versioned bucket).

      url = bucket_url.Clone()
      url.object_name = tracker_object.object_name
      url.generation = tracker_object.generation
      existing_objects_to_delete.append(url)
      continue

    dst_arg = dst_args[tracker_object.object_name]
    file_part = FilePart(dst_arg.filename, dst_arg.file_start,
                         dst_arg.file_length)
    # TODO: calculate MD5's in parallel when possible.
    content_md5 = CalculateB64EncodedMd5FromContents(file_part)

    try:
      # Get the MD5 of the currently-existing component.
      dst_url = dst_arg.dst_url
      dst_metadata = gsutil_api.GetObjectMetadata(
          dst_url.bucket_name, dst_url.object_name,
          generation=dst_url.generation, provider=dst_url.scheme,
          fields=['md5Hash', 'etag'])
      cloud_md5 = dst_metadata.md5Hash
    except Exception:  # pylint: disable=broad-except
      # We don't actually care what went wrong - we couldn't retrieve the
      # object to check the MD5, so just upload it again.
      cloud_md5 = None

    if cloud_md5 != content_md5:
      components_to_upload.append(dst_arg)
      objects_already_chosen.append(tracker_object.object_name)
      if tracker_object.generation:
        # If the old object doesn't have a generation (i.e., it isn't in a
        # versioned bucket), then we will just overwrite it anyway.
        invalid_component_with_generation = dst_arg.dst_url.Clone()
        invalid_component_with_generation.generation = tracker_object.generation
        existing_objects_to_delete.append(invalid_component_with_generation)
    else:
      url = dst_arg.dst_url.Clone()
      url.generation = tracker_object.generation
      uploaded_components.append(url)
      objects_already_chosen.append(tracker_object.object_name)

  if uploaded_components:
    logging.info('Found %d existing temporary components to reuse.',
                 len(uploaded_components))

  return (components_to_upload, uploaded_components,
          existing_objects_to_delete)
