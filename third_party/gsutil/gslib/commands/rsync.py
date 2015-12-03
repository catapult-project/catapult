# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.
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
"""Implementation of Unix-like rsync command."""

from __future__ import absolute_import

import errno
import heapq
import io
from itertools import islice
import os
import re
import tempfile
import textwrap
import traceback
import urllib

from boto import config
import crcmod

from gslib import copy_helper
from gslib.bucket_listing_ref import BucketListingObject
from gslib.cloud_api import NotFoundException
from gslib.command import Command
from gslib.command import DummyArgChecker
from gslib.command_argument import CommandArgument
from gslib.copy_helper import CreateCopyHelperOpts
from gslib.copy_helper import SkipUnsupportedObjectError
from gslib.cs_api_map import ApiSelector
from gslib.exception import CommandException
from gslib.hashing_helper import CalculateB64EncodedCrc32cFromContents
from gslib.hashing_helper import CalculateB64EncodedMd5FromContents
from gslib.hashing_helper import SLOW_CRCMOD_WARNING
from gslib.plurality_checkable_iterator import PluralityCheckableIterator
from gslib.sig_handling import GetCaughtSignals
from gslib.sig_handling import RegisterSignalHandler
from gslib.storage_url import StorageUrlFromString
from gslib.util import GetCloudApiInstance
from gslib.util import IsCloudSubdirPlaceholder
from gslib.util import TEN_MIB
from gslib.util import UsingCrcmodExtension
from gslib.util import UTF8
from gslib.wildcard_iterator import CreateWildcardIterator


_SYNOPSIS = """
  gsutil rsync [-c] [-C] [-d] [-e] [-n] [-p] [-r] [-U] [-x] src_url dst_url
"""

_DETAILED_HELP_TEXT = ("""
<B>SYNOPSIS</B>
""" + _SYNOPSIS + """


<B>DESCRIPTION</B>
  The gsutil rsync command makes the contents under dst_url the same as the
  contents under src_url, by copying any missing files/objects, and (if the
  -d option is specified) deleting any extra files/objects. For example, to
  make gs://mybucket/data match the contents of the local directory "data"
  you could do:

    gsutil rsync -d data gs://mybucket/data

  To recurse into directories use the -r option:

    gsutil rsync -d -r data gs://mybucket/data

  To copy only new/changed files without deleting extra files from
  gs://mybucket/data leave off the -d option:

    gsutil rsync -r data gs://mybucket/data

  If you have a large number of objects to synchronize you might want to use the
  gsutil -m option, to perform parallel (multi-threaded/multi-processing)
  synchronization:

    gsutil -m rsync -d -r data gs://mybucket/data

  The -m option typically will provide a large performance boost if either the
  source or destination (or both) is a cloud URL. If both source and
  destination are file URLs the -m option will typically thrash the disk and
  slow synchronization down.

  To make the local directory "data" the same as the contents of
  gs://mybucket/data:

    gsutil rsync -d -r gs://mybucket/data data

  To make the contents of gs://mybucket2 the same as gs://mybucket1:

    gsutil rsync -d -r gs://mybucket1 gs://mybucket2

  You can also mirror data across local directories:

    gsutil rsync -d -r dir1 dir2

  To mirror your content across clouds:

    gsutil rsync -d -r gs://my-gs-bucket s3://my-s3-bucket

  Note: If you are synchronizing a large amount of data between clouds you might
  consider setting up a
  `Google Compute Engine <https://cloud.google.com/products/compute-engine>`_
  account and running gsutil there. Since cross-provider gsutil data transfers
  flow through the machine where gsutil is running, doing this can make your
  transfer run significantly faster than running gsutil on your local
  workstation.


<B>BE CAREFUL WHEN USING -d OPTION!</B>
  The rsync -d option is very useful and commonly used, because it provides a
  means of making the contents of a destination bucket or directory match those
  of a source bucket or directory. However, please exercise caution when you
  use this option: It's possible to delete large amounts of data accidentally
  if, for example, you erroneously reverse source and destination. For example,
  if you meant to synchronize a local directory from a bucket in the cloud but
  instead run the command:

    gsutil -m rsync -r -d ./your-dir gs://your-bucket

  and your-dir is currently empty, you will quickly delete all of the objects in
  gs://your-bucket.

  You can also cause large amounts of data to be lost quickly by specifying a
  subdirectory of the destination as the source of an rsync. For example, the
  command:

    gsutil -m rsync -r -d gs://your-bucket/data gs://your-bucket

  would cause most or all of the objects in gs://your-bucket to be deleted
  (some objects may survive if there are any with names that sort lower than
  "data" under gs://your-bucket/data).

  In addition to paying careful attention to the source and destination you
  specify with the rsync command, there are two more safety measures your can
  take when using gsutil rsync -d:

    1. Try running the command with the rsync -n option first, to see what it
       would do without actually performing the operations. For example, if
       you run the command:

         gsutil -m rsync -r -d -n gs://your-bucket/data gs://your-bucket
       
       it will be immediately evident that running that command without the -n
       option would cause many objects to be deleted.

    2. Enable object versioning in your bucket, which will allow you to restore
       objects if you accidentally delete them. For more details see
       "gsutil help versions".


<B>IMPACT OF BUCKET LISTING EVENTUAL CONSISTENCY</B>
  The rsync command operates by listing the source and destination URLs, and
  then performing copy and remove operations according to the differences
  between these listings. Because bucket listing is eventually (not strongly)
  consistent, if you upload new objects or delete objects from a bucket and then
  immediately run gsutil rsync with that bucket as the source or destination,
  it's possible the rsync command will not see the recent updates and thus
  synchronize incorrectly. You can rerun the rsync operation again later to
  correct the incorrect synchronization.


<B>CHECKSUM VALIDATION AND FAILURE HANDLING</B>
  At the end of every upload or download, the gsutil rsync command validates
  that the checksum of the source file/object matches the checksum of the
  destination file/object. If the checksums do not match, gsutil will delete
  the invalid copy and print a warning message. This very rarely happens, but
  if it does, please contact gs-team@google.com.

  The rsync command will retry when failures occur, but if enough failures
  happen during a particular copy or delete operation the command will skip that
  object and move on. At the end of the synchronization run if any failures were
  not successfully retried, the rsync command will report the count of failures,
  and exit with non-zero status. At this point you can run the rsync command
  again, and it will attempt any remaining needed copy and/or delete operations.

  Note that there are cases where retrying will never succeed, such as if you
  don't have write permission to the destination bucket or if the destination
  path for some objects is longer than the maximum allowed length.

  For more details about gsutil's retry handling, please see
  "gsutil help retries".


<B>CHANGE DETECTION ALGORITHM</B>
  To determine if a file or object has changed gsutil rsync first checks whether
  the source and destination sizes match. If they match, it next checks if their
  checksums match, using checksums if available (see below). Unlike the Unix
  rsync command, gsutil rsync does not use timestamps to determine if the
  file/object changed, because the GCS API does not permit the caller to set an
  object's timestamp (hence, timestamps of identical files/objects cannot be
  made to match).

  Checksums will not be available in two cases:

  1. When synchronizing to or from a file system. By default, gsutil does not
     checksum files, because of the slowdown caused when working with large
     files. You can cause gsutil to checksum files by using the gsutil rsync -c
     option, at the cost of increased local disk I/O and run time when working
     with large files. You should consider using the -c option if your files can
     change without changing sizes (e.g., if you have files that contain fixed
     width data, such as timestamps).

  2. When comparing composite GCS objects with objects at a cloud provider that
     does not support CRC32C (which is the only checksum available for composite
     objects). See 'gsutil help compose' for details about composite objects.


<B>COPYING IN THE CLOUD AND METADATA PRESERVATION</B>
  If both the source and destination URL are cloud URLs from the same provider,
  gsutil copies data "in the cloud" (i.e., without downloading to and uploading
  from the machine where you run gsutil). In addition to the performance and
  cost advantages of doing this, copying in the cloud preserves metadata (like
  Content-Type and Cache-Control). In contrast, when you download data from the
  cloud it ends up in a file, which has no associated metadata. Thus, unless you
  have some way to hold on to or re-create that metadata, synchronizing a bucket
  to a directory in the local file system will not retain the metadata.

  Note that by default, the gsutil rsync command does not copy the ACLs of
  objects being synchronized and instead will use the default bucket ACL (see
  "gsutil help defacl"). You can override this behavior with the -p option (see
  OPTIONS below).


<B>SLOW CHECKSUMS</B>
  If you find that CRC32C checksum computation runs slowly, this is likely
  because you don't have a compiled CRC32c on your system. Try running:

    gsutil ver -l

  If the output contains:

    compiled crcmod: False

  you are running a Python library for computing CRC32C, which is much slower
  than using the compiled code. For information on getting a compiled CRC32C
  implementation, see 'gsutil help crc32c'.


<B>LIMITATIONS</B>
  1. The gsutil rsync command doesn't make the destination object's timestamps
     match those of the source object (it can't; timestamp setting is not
     allowed by the GCS API).

  2. The gsutil rsync command considers only the current object generations in
     the source and destination buckets when deciding what to copy / delete. If
     versioning is enabled in the destination bucket then gsutil rsync's
     overwriting or deleting objects will end up creating versions, but the
     command doesn't try to make the archived generations match in the source
     and destination buckets.



<B>OPTIONS</B>
  -c            Causes the rsync command to compute checksums for files if the
                size of source and destination match, and then compare
                checksums.  This option increases local disk I/O and run time
                if either src_url or dst_url are on the local file system.

  -C            If an error occurs, continue to attempt to copy the remaining
                files. If errors occurred, gsutil's exit status will be non-zero
                even if this flag is set. This option is implicitly set when
                running "gsutil -m rsync...".  Note: -C only applies to the
                actual copying operation. If an error occurs while iterating
                over the files in the local directory (e.g., invalid Unicode
                file name) gsutil will print an error message and abort.

  -d            Delete extra files under dst_url not found under src_url. By
                default extra files are not deleted. Note: this option can
                delete data quickly if you specify the wrong source/destination
                combination. See the help section above,
                "BE CAREFUL WHEN USING -d OPTION!".

  -e            Exclude symlinks. When specified, symbolic links will be
                ignored.

  -n            Causes rsync to run in "dry run" mode, i.e., just outputting
                what would be copied or deleted without actually doing any
                copying/deleting.

  -p            Causes ACLs to be preserved when synchronizing in the cloud.
                Note that this option has performance and cost implications when
                using the XML API, as it requires separate HTTP calls for
                interacting with ACLs. The performance issue can be mitigated to
                some degree by using gsutil -m rsync to cause parallel
                synchronization. Also, this option only works if you have OWNER
                access to all of the objects that are copied.

                You can avoid the additional performance and cost of using
                rsync -p if you want all objects in the destination bucket to
                end up with the same ACL by setting a default object ACL on that
                bucket instead of using rsync -p. See 'help gsutil defacl'.

  -R, -r        Causes directories, buckets, and bucket subdirectories to be
                synchronized recursively. If you neglect to use this option
                gsutil will make only the top-level directory in the source
                and destination URLs match, skipping any sub-directories.

  -U            Skip objects with unsupported object types instead of failing.
                Unsupported object types are Amazon S3 Objects in the GLACIER
                storage class.

  -x pattern    Causes files/objects matching pattern to be excluded, i.e., any
                matching files/objects will not be copied or deleted. Note that
                the pattern is a Python regular expression, not a wildcard (so,
                matching any string ending in 'abc' would be specified using
                '.*abc' rather than '*abc'). Note also that the exclude path is
                always relative (similar to Unix rsync or tar exclude options).
                For example, if you run the command:

                  gsutil rsync -x 'data./.*\\.txt' dir gs://my-bucket

                it will skip the file dir/data1/a.txt.

                You can use regex alternation to specify multiple exclusions,
                for example:

                  gsutil rsync -x '.*\\.txt|.*\\.jpg' dir gs://my-bucket
""")


class _DiffAction(object):
  COPY = 'copy'
  REMOVE = 'remove'


_NA = '-'
_OUTPUT_BUFFER_SIZE = 64 * 1024
_PROGRESS_REPORT_LISTING_COUNT = 10000


# Tracks files we need to clean up at end or if interrupted.
_tmp_files = []


# pylint: disable=unused-argument
def _HandleSignals(signal_num, cur_stack_frame):
  """Called when rsync command is killed with SIGINT, SIGQUIT or SIGTERM."""
  CleanUpTempFiles()


def CleanUpTempFiles():
  """Cleans up temp files.

  This function allows the main (RunCommand) function to clean up at end of
  operation, or if gsutil rsync is interrupted (e.g., via ^C). This is necessary
  because tempfile.NamedTemporaryFile doesn't allow the created file to be
  re-opened in read mode on Windows, so we have to use tempfile.mkstemp, which
  doesn't automatically delete temp files.
  """
  try:
    for fname in _tmp_files:
      os.unlink(fname)
  except:  # pylint: disable=bare-except
    pass


class _DiffToApply(object):
  """Class that encapsulates info needed to apply diff for one object."""

  def __init__(self, src_url_str, dst_url_str, diff_action):
    """Constructor.

    Args:
      src_url_str: The source URL string, or None if diff_action is REMOVE.
      dst_url_str: The destination URL string.
      diff_action: _DiffAction to be applied.
    """
    self.src_url_str = src_url_str
    self.dst_url_str = dst_url_str
    self.diff_action = diff_action


def _DiffToApplyArgChecker(command_instance, diff_to_apply):
  """Arg checker that skips symlinks if -e flag specified."""
  if (diff_to_apply.diff_action == _DiffAction.REMOVE
      or not command_instance.exclude_symlinks):
    # No src URL is populated for REMOVE actions.
    return True
  exp_src_url = StorageUrlFromString(diff_to_apply.src_url_str)
  if exp_src_url.IsFileUrl() and os.path.islink(exp_src_url.object_name):
    command_instance.logger.info('Skipping symbolic link %s...', exp_src_url)
    return False
  return True


def _ComputeNeededFileChecksums(logger, src_url_str, src_size, src_crc32c,
                                src_md5, dst_url_str, dst_size, dst_crc32c,
                                dst_md5):
  """Computes any file checksums needed by _ObjectsMatch.

  Args:
    logger: logging.logger for outputting log messages.
    src_url_str: Source URL string.
    src_size: Source size
    src_crc32c: Source CRC32c.
    src_md5: Source MD5.
    dst_url_str: Destination URL string.
    dst_size: Destination size
    dst_crc32c: Destination CRC32c.
    dst_md5: Destination MD5.

  Returns:
    (src_crc32c, src_md5, dst_crc32c, dst_md5)
  """
  src_url = StorageUrlFromString(src_url_str)
  dst_url = StorageUrlFromString(dst_url_str)
  if src_url.IsFileUrl():
    if dst_crc32c != _NA or dst_url.IsFileUrl():
      if src_size > TEN_MIB:
        logger.info('Computing MD5 for %s...', src_url_str)
      with open(src_url.object_name, 'rb') as fp:
        src_crc32c = CalculateB64EncodedCrc32cFromContents(fp)
    elif dst_md5 != _NA or dst_url.IsFileUrl():
      if dst_size > TEN_MIB:
        logger.info('Computing MD5 for %s...', dst_url_str)
      with open(src_url.object_name, 'rb') as fp:
        src_md5 = CalculateB64EncodedMd5FromContents(fp)
  if dst_url.IsFileUrl():
    if src_crc32c != _NA:
      if src_size > TEN_MIB:
        logger.info('Computing CRC32C for %s...', src_url_str)
      with open(dst_url.object_name, 'rb') as fp:
        dst_crc32c = CalculateB64EncodedCrc32cFromContents(fp)
    elif src_md5 != _NA:
      if dst_size > TEN_MIB:
        logger.info('Computing CRC32C for %s...', dst_url_str)
      with open(dst_url.object_name, 'rb') as fp:
        dst_md5 = CalculateB64EncodedMd5FromContents(fp)
  return (src_crc32c, src_md5, dst_crc32c, dst_md5)


def _ListUrlRootFunc(cls, args_tuple, thread_state=None):
  """Worker function for listing files/objects under to be sync'd.

  Outputs sorted list to out_file_name, formatted per _BuildTmpOutputLine. We
  sort the listed URLs because we don't want to depend on consistent sort
  order across file systems and cloud providers.

  Args:
    cls: Command instance.
    args_tuple: (base_url_str, out_file_name, desc), where base_url_str is
                top-level URL string to list; out_filename is name of file to
                which sorted output should be written; desc is 'source' or
                'destination'.
    thread_state: gsutil Cloud API instance to use.
  """
  gsutil_api = GetCloudApiInstance(cls, thread_state=thread_state)
  (base_url_str, out_filename, desc) = args_tuple
  # We sort while iterating over base_url_str, allowing parallelism of batched
  # sorting with collecting the listing.
  out_file = io.open(out_filename, mode='w', encoding=UTF8)
  try:
    _BatchSort(_FieldedListingIterator(cls, gsutil_api, base_url_str, desc),
               out_file)
  except Exception as e:  # pylint: disable=broad-except
    # Abandon rsync if an exception percolates up to this layer - retryable
    # exceptions are handled in the lower layers, so we got a non-retryable
    # exception (like 404 bucket not found) and proceeding would either be
    # futile or could result in data loss - for example:
    #     gsutil rsync -d gs://non-existent-bucket ./localdir
    # would delete files from localdir.
    cls.logger.error(
        'Caught non-retryable exception while listing %s: %s' %
        (base_url_str, e))
    cls.non_retryable_listing_failures = 1
  out_file.close()


def _LocalDirIterator(base_url):
  """A generator that yields a BLR for each file in a local directory.

     We use this function instead of WildcardIterator for listing a local
     directory without recursion, because the glob.globi implementation called
     by WildcardIterator skips "dot" files (which we don't want to do when
     synchronizing to or from a local directory).

  Args:
    base_url: URL for the directory over which to iterate.

  Yields:
    BucketListingObject for each file in the directory.
  """
  for filename in os.listdir(base_url.object_name):
    filename = os.path.join(base_url.object_name, filename)
    if os.path.isfile(filename):
      yield BucketListingObject(StorageUrlFromString(filename), None)


def _FieldedListingIterator(cls, gsutil_api, base_url_str, desc):
  """Iterator over base_url_str formatting output per _BuildTmpOutputLine.

  Args:
    cls: Command instance.
    gsutil_api: gsutil Cloud API instance to use for bucket listing.
    base_url_str: The top-level URL string over which to iterate.
    desc: 'source' or 'destination'.

  Yields:
    Output line formatted per _BuildTmpOutputLine.
  """
  base_url = StorageUrlFromString(base_url_str)
  if base_url.scheme == 'file' and not cls.recursion_requested:
    iterator = _LocalDirIterator(base_url)
  else:
    if cls.recursion_requested:
      wildcard = '%s/**' % base_url_str.rstrip('/\\')
    else:
      wildcard = '%s/*' % base_url_str.rstrip('/\\')
    iterator = CreateWildcardIterator(
        wildcard, gsutil_api, debug=cls.debug,
        project_id=cls.project_id).IterObjects(
            # Request just the needed fields, to reduce bandwidth usage.
            bucket_listing_fields=['crc32c', 'md5Hash', 'name', 'size'])

  i = 0
  for blr in iterator:
    # Various GUI tools (like the GCS web console) create placeholder objects
    # ending with '/' when the user creates an empty directory. Normally these
    # tools should delete those placeholders once objects have been written
    # "under" the directory, but sometimes the placeholders are left around.
    # We need to filter them out here, otherwise if the user tries to rsync
    # from GCS to a local directory it will result in a directory/file
    # conflict (e.g., trying to download an object called "mydata/" where the
    # local directory "mydata" exists).
    url = blr.storage_url
    if IsCloudSubdirPlaceholder(url, blr=blr):
      # We used to output the message 'Skipping cloud sub-directory placeholder
      # object...' but we no longer do so because it caused customer confusion.
      continue
    if (cls.exclude_symlinks and url.IsFileUrl()
        and os.path.islink(url.object_name)):
      continue
    if cls.exclude_pattern:
      str_to_check = url.url_string[len(base_url_str):]
      if str_to_check.startswith(url.delim):
        str_to_check = str_to_check[1:]
      if cls.exclude_pattern.match(str_to_check):
        continue
    i += 1
    if i % _PROGRESS_REPORT_LISTING_COUNT == 0:
      cls.logger.info('At %s listing %d...', desc, i)
    yield _BuildTmpOutputLine(blr)


def _BuildTmpOutputLine(blr):
  """Builds line to output to temp file for given BucketListingRef.

  Args:
    blr: The BucketListingRef.

  Returns:
    The output line, formatted as _EncodeUrl(URL)<sp>size<sp>crc32c<sp>md5
    where crc32c will only be present for GCS URLs, and md5 will only be
    present for cloud URLs that aren't composite objects. A missing field is
    populated with '-'.
  """
  crc32c = _NA
  md5 = _NA
  url = blr.storage_url
  if url.IsFileUrl():
    size = os.path.getsize(url.object_name)
  elif url.IsCloudUrl():
    size = blr.root_object.size
    crc32c = blr.root_object.crc32c or _NA
    md5 = blr.root_object.md5Hash or _NA
  else:
    raise CommandException('Got unexpected URL type (%s)' % url.scheme)
  return '%s %d %s %s\n' % (_EncodeUrl(url.url_string), size, crc32c, md5)


def _EncodeUrl(url_string):
  """Encodes url_str with quote plus encoding and UTF8 character encoding.

  We use this for all URL encodings.

  Args:
    url_string: String URL to encode.

  Returns:
    encoded URL.
  """
  return urllib.quote_plus(url_string.encode(UTF8))


def _DecodeUrl(enc_url_string):
  """Inverts encoding from EncodeUrl.

  Args:
    enc_url_string: String URL to decode.

  Returns:
    decoded URL.
  """
  return urllib.unquote_plus(enc_url_string).decode(UTF8)


# pylint: disable=bare-except
def _BatchSort(in_iter, out_file):
  """Sorts input lines from in_iter and outputs to out_file.

  Sorts in batches as input arrives, so input file does not need to be loaded
  into memory all at once. Derived from Python Recipe 466302: Sorting big
  files the Python 2.4 way by Nicolas Lehuen.

  Sorted format is per _BuildTmpOutputLine. We're sorting on the entire line
  when we could just sort on the first record (URL); but the sort order is
  identical either way.

  Args:
    in_iter: Input iterator.
    out_file: Output file.
  """
  # Note: If chunk_files gets very large we can run out of open FDs. See .boto
  # file comments about rsync_buffer_lines. If increasing rsync_buffer_lines
  # doesn't suffice (e.g., for someone synchronizing with a really large
  # bucket), an option would be to make gsutil merge in passes, never
  # opening all chunk files simultaneously.
  buffer_size = config.getint('GSUtil', 'rsync_buffer_lines', 32000)
  chunk_files = []
  try:
    while True:
      current_chunk = sorted(islice(in_iter, buffer_size))
      if not current_chunk:
        break
      output_chunk = io.open('%s-%06i' % (out_file.name, len(chunk_files)),
                             mode='w+', encoding=UTF8)
      chunk_files.append(output_chunk)
      output_chunk.writelines(unicode(''.join(current_chunk)))
      output_chunk.flush()
      output_chunk.seek(0)
    out_file.writelines(heapq.merge(*chunk_files))
  except IOError as e:
    if e.errno == errno.EMFILE:
      raise CommandException('\n'.join(textwrap.wrap(
          'Synchronization failed because too many open file handles were '
          'needed while building synchronization state. Please see the '
          'comments about rsync_buffer_lines in your .boto config file for a '
          'possible way to address this problem.')))
    raise
  finally:
    for chunk_file in chunk_files:
      try:
        chunk_file.close()
        os.remove(chunk_file.name)
      except:
        pass


class _DiffIterator(object):
  """Iterator yielding sequence of _DiffToApply objects."""

  def __init__(self, command_obj, base_src_url, base_dst_url):
    self.command_obj = command_obj
    self.compute_file_checksums = command_obj.compute_file_checksums
    self.delete_extras = command_obj.delete_extras
    self.recursion_requested = command_obj.recursion_requested
    self.logger = self.command_obj.logger
    self.base_src_url = base_src_url
    self.base_dst_url = base_dst_url
    self.logger.info('Building synchronization state...')

    (src_fh, self.sorted_list_src_file_name) = tempfile.mkstemp(
        prefix='gsutil-rsync-src-')
    _tmp_files.append(self.sorted_list_src_file_name)
    (dst_fh, self.sorted_list_dst_file_name) = tempfile.mkstemp(
        prefix='gsutil-rsync-dst-')
    _tmp_files.append(self.sorted_list_dst_file_name)
    # Close the file handles; the file will be opened in write mode by
    # _ListUrlRootFunc.
    os.close(src_fh)
    os.close(dst_fh)

    # Build sorted lists of src and dst URLs in parallel. To do this, pass args
    # to _ListUrlRootFunc as tuple (base_url_str, out_filename, desc)
    # where base_url_str is the starting URL string for listing.
    args_iter = iter([
        (self.base_src_url.url_string, self.sorted_list_src_file_name,
         'source'),
        (self.base_dst_url.url_string, self.sorted_list_dst_file_name,
         'destination')
    ])

    # Contains error message from non-retryable listing failure.
    command_obj.non_retryable_listing_failures = 0
    shared_attrs = ['non_retryable_listing_failures']
    command_obj.Apply(_ListUrlRootFunc, args_iter, _RootListingExceptionHandler,
                      shared_attrs, arg_checker=DummyArgChecker,
                      parallel_operations_override=True,
                      fail_on_error=True)

    if command_obj.non_retryable_listing_failures:
      raise CommandException('Caught non-retryable exception - aborting rsync')

    self.sorted_list_src_file = open(self.sorted_list_src_file_name, 'r')
    self.sorted_list_dst_file = open(self.sorted_list_dst_file_name, 'r')

    # Wrap iterators in PluralityCheckableIterator so we can check emptiness.
    self.sorted_src_urls_it = PluralityCheckableIterator(
        iter(self.sorted_list_src_file))
    self.sorted_dst_urls_it = PluralityCheckableIterator(
        iter(self.sorted_list_dst_file))

  def _ParseTmpFileLine(self, line):
    """Parses output from _BuildTmpOutputLine.

    Parses into tuple:
      (URL, size, crc32c, md5)
    where crc32c and/or md5 can be _NA.

    Args:
      line: The line to parse.

    Returns:
      Parsed tuple: (url, size, crc32c, md5)
    """
    (encoded_url, size, crc32c, md5) = line.split()
    return (_DecodeUrl(encoded_url), int(size), crc32c, md5.strip())

  def _WarnIfMissingCloudHash(self, url_str, crc32c, md5):
    """Warns if given url_str is a cloud URL and is missing both crc32c and md5.

    Args:
      url_str: Destination URL string.
      crc32c: Destination CRC32c.
      md5: Destination MD5.

    Returns:
      True if issued warning.
    """
    # One known way this can currently happen is when rsync'ing objects larger
    # than 5 GB from S3 (for which the etag is not an MD5).
    if (StorageUrlFromString(url_str).IsCloudUrl()
        and crc32c == _NA and md5 == _NA):
      self.logger.warn(
          'Found no hashes to validate %s. Integrity cannot be assured without '
          'hashes.', url_str)
      return True
    return False

  def _ObjectsMatch(self, src_url_str, src_size, src_crc32c, src_md5,
                    dst_url_str, dst_size, dst_crc32c, dst_md5):
    """Returns True if src and dst objects are the same.

    Uses size plus whatever checksums are available.

    Args:
      src_url_str: Source URL string.
      src_size: Source size
      src_crc32c: Source CRC32c.
      src_md5: Source MD5.
      dst_url_str: Destination URL string.
      dst_size: Destination size
      dst_crc32c: Destination CRC32c.
      dst_md5: Destination MD5.

    Returns:
      True/False.
    """
    # Note: This function is called from __iter__, which is called from the
    # Command.Apply driver. Thus, all checksum computation will be run in a
    # single thread, which is good (having multiple threads concurrently
    # computing checksums would thrash the disk).
    if src_size != dst_size:
      return False
    if self.compute_file_checksums:
      (src_crc32c, src_md5, dst_crc32c, dst_md5) = _ComputeNeededFileChecksums(
          self.logger, src_url_str, src_size, src_crc32c, src_md5, dst_url_str,
          dst_size, dst_crc32c, dst_md5)
    if src_md5 != _NA and dst_md5 != _NA:
      self.logger.debug('Comparing md5 for %s and %s', src_url_str, dst_url_str)
      return src_md5 == dst_md5
    if src_crc32c != _NA and dst_crc32c != _NA:
      self.logger.debug(
          'Comparing crc32c for %s and %s', src_url_str, dst_url_str)
      return src_crc32c == dst_crc32c
    if not self._WarnIfMissingCloudHash(src_url_str, src_crc32c, src_md5):
      self._WarnIfMissingCloudHash(dst_url_str, dst_crc32c, dst_md5)
    # Without checksums to compare we depend only on basic size comparison.
    return True

  def __iter__(self):
    """Iterates over src/dst URLs and produces a _DiffToApply sequence.

    Yields:
      The _DiffToApply.
    """
    # Strip trailing slashes, if any, so we compute tail length against
    # consistent position regardless of whether trailing slashes were included
    # or not in URL.
    base_src_url_len = len(self.base_src_url.url_string.rstrip('/\\'))
    base_dst_url_len = len(self.base_dst_url.url_string.rstrip('/\\'))
    src_url_str = dst_url_str = None
    # Invariant: After each yield, the URLs in src_url_str, dst_url_str,
    # self.sorted_src_urls_it, and self.sorted_dst_urls_it are not yet
    # processed. Each time we encounter None in src_url_str or dst_url_str we
    # populate from the respective iterator, and we reset one or the other value
    # to None after yielding an action that disposes of that URL.
    while not self.sorted_src_urls_it.IsEmpty() or src_url_str is not None:
      if src_url_str is None:
        (src_url_str, src_size, src_crc32c, src_md5) = self._ParseTmpFileLine(
            self.sorted_src_urls_it.next())
        # Skip past base URL and normalize slashes so we can compare across
        # clouds/file systems (including Windows).
        src_url_str_to_check = _EncodeUrl(
            src_url_str[base_src_url_len:].replace('\\', '/'))
        dst_url_str_would_copy_to = copy_helper.ConstructDstUrl(
            self.base_src_url, StorageUrlFromString(src_url_str), True, True,
            self.base_dst_url, False, self.recursion_requested).url_string
      if self.sorted_dst_urls_it.IsEmpty():
        # We've reached end of dst URLs, so copy src to dst.
        yield _DiffToApply(
            src_url_str, dst_url_str_would_copy_to, _DiffAction.COPY)
        src_url_str = None
        continue
      if not dst_url_str:
        (dst_url_str, dst_size, dst_crc32c, dst_md5) = (
            self._ParseTmpFileLine(self.sorted_dst_urls_it.next()))
        # Skip past base URL and normalize slashes so we can compare acros
        # clouds/file systems (including Windows).
        dst_url_str_to_check = _EncodeUrl(
            dst_url_str[base_dst_url_len:].replace('\\', '/'))

      if src_url_str_to_check < dst_url_str_to_check:
        # There's no dst object corresponding to src object, so copy src to dst.
        yield _DiffToApply(
            src_url_str, dst_url_str_would_copy_to, _DiffAction.COPY)
        src_url_str = None
      elif src_url_str_to_check > dst_url_str_to_check:
        # dst object without a corresponding src object, so remove dst if -d
        # option was specified.
        if self.delete_extras:
          yield _DiffToApply(None, dst_url_str, _DiffAction.REMOVE)
        dst_url_str = None
      else:
        # There is a dst object corresponding to src object, so check if objects
        # match.
        if self._ObjectsMatch(
            src_url_str, src_size, src_crc32c, src_md5,
            dst_url_str, dst_size, dst_crc32c, dst_md5):
          # Continue iterating without yielding a _DiffToApply.
          pass
        else:
          yield _DiffToApply(src_url_str, dst_url_str, _DiffAction.COPY)
        src_url_str = None
        dst_url_str = None

    # If -d option specified any files/objects left in dst iteration should be
    # removed.
    if not self.delete_extras:
      return
    if dst_url_str:
      yield _DiffToApply(None, dst_url_str, _DiffAction.REMOVE)
      dst_url_str = None
    for line in self.sorted_dst_urls_it:
      (dst_url_str, _, _, _) = self._ParseTmpFileLine(line)
      yield _DiffToApply(None, dst_url_str, _DiffAction.REMOVE)


def _RsyncFunc(cls, diff_to_apply, thread_state=None):
  """Worker function for performing the actual copy and remove operations."""
  gsutil_api = GetCloudApiInstance(cls, thread_state=thread_state)
  dst_url_str = diff_to_apply.dst_url_str
  dst_url = StorageUrlFromString(dst_url_str)
  if diff_to_apply.diff_action == _DiffAction.REMOVE:
    if cls.dryrun:
      cls.logger.info('Would remove %s', dst_url)
    else:
      cls.logger.info('Removing %s', dst_url)
      if dst_url.IsFileUrl():
        os.unlink(dst_url.object_name)
      else:
        try:
          gsutil_api.DeleteObject(
              dst_url.bucket_name, dst_url.object_name,
              generation=dst_url.generation, provider=dst_url.scheme)
        except NotFoundException:
          # If the object happened to be deleted by an external process, this
          # is fine because it moves us closer to the desired state.
          pass
  elif diff_to_apply.diff_action == _DiffAction.COPY:
    src_url_str = diff_to_apply.src_url_str
    src_url = StorageUrlFromString(src_url_str)
    if cls.dryrun:
      cls.logger.info('Would copy %s to %s', src_url, dst_url)
    else:
      try:
        copy_helper.PerformCopy(cls.logger, src_url, dst_url, gsutil_api, cls,
                                _RsyncExceptionHandler,
                                headers=cls.headers)
      except SkipUnsupportedObjectError, e:
        cls.logger.info('Skipping item %s with unsupported object type %s',
                        src_url, e.unsupported_type)

  else:
    raise CommandException('Got unexpected DiffAction (%d)'
                           % diff_to_apply.diff_action)


def _RootListingExceptionHandler(cls, e):
  """Simple exception handler for exceptions during listing URLs to sync."""
  cls.logger.error(str(e))


def _RsyncExceptionHandler(cls, e):
  """Simple exception handler to allow post-completion status."""
  cls.logger.error(str(e))
  cls.op_failure_count += 1
  cls.logger.debug('\n\nEncountered exception while syncing:\n%s\n',
                   traceback.format_exc())


class RsyncCommand(Command):
  """Implementation of gsutil rsync command."""

  # Command specification. See base class for documentation.
  command_spec = Command.CreateCommandSpec(
      'rsync',
      command_name_aliases=[],
      usage_synopsis=_SYNOPSIS,
      min_args=2,
      max_args=2,
      supported_sub_args='cCdenprRUx:',
      file_url_ok=True,
      provider_url_ok=False,
      urls_start_arg=0,
      gs_api_support=[ApiSelector.XML, ApiSelector.JSON],
      gs_default_api=ApiSelector.JSON,
      argparse_arguments=[
          CommandArgument.MakeNCloudOrFileURLsArgument(2)
      ]
  )
  # Help specification. See help_provider.py for documentation.
  help_spec = Command.HelpSpec(
      help_name='rsync',
      help_name_aliases=['sync', 'synchronize'],
      help_type='command_help',
      help_one_line_summary='Synchronize content of two buckets/directories',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
  total_bytes_transferred = 0

  def _InsistContainer(self, url_str, treat_nonexistent_object_as_subdir):
    """Sanity checks that URL names an existing container.

    Args:
      url_str: URL string to check.
      treat_nonexistent_object_as_subdir: indicates if should treat a
                                          non-existent object as a subdir.

    Returns:
      URL for checked string.

    Raises:
      CommandException if url_str doesn't name an existing container.
    """
    (url, have_existing_container) = (
        copy_helper.ExpandUrlToSingleBlr(url_str, self.gsutil_api, self.debug,
                                         self.project_id,
                                         treat_nonexistent_object_as_subdir))
    if not have_existing_container:
      raise CommandException(
          'arg (%s) does not name a directory, bucket, or bucket subdir.'
          % url_str)
    return url

  def RunCommand(self):
    """Command entry point for the rsync command."""
    self._ParseOpts()
    if self.compute_file_checksums and not UsingCrcmodExtension(crcmod):
      self.logger.warn(SLOW_CRCMOD_WARNING)

    src_url = self._InsistContainer(self.args[0], False)
    dst_url = self._InsistContainer(self.args[1], True)

    # Tracks if any copy or rm operations failed.
    self.op_failure_count = 0

    # List of attributes to share/manage across multiple processes in
    # parallel (-m) mode.
    shared_attrs = ['op_failure_count']

    for signal_num in GetCaughtSignals():
      RegisterSignalHandler(signal_num, _HandleSignals)

    # Perform sync requests in parallel (-m) mode, if requested, using
    # configured number of parallel processes and threads. Otherwise,
    # perform requests with sequential function calls in current process.
    diff_iterator = _DiffIterator(self, src_url, dst_url)
    self.logger.info('Starting synchronization')
    try:
      self.Apply(_RsyncFunc, diff_iterator, _RsyncExceptionHandler,
                 shared_attrs, arg_checker=_DiffToApplyArgChecker,
                 fail_on_error=True)
    finally:
      CleanUpTempFiles()

    if self.op_failure_count:
      plural_str = 's' if self.op_failure_count else ''
      raise CommandException(
          '%d file%s/object%s could not be copied/removed.' %
          (self.op_failure_count, plural_str, plural_str))

  def _ParseOpts(self):
    # exclude_symlinks is handled by Command parent class, so save in Command
    # state rather than CopyHelperOpts.
    self.exclude_symlinks = False
    # continue_on_error is handled by Command parent class, so save in Command
    # state rather than CopyHelperOpts.
    self.continue_on_error = False
    self.delete_extras = False
    preserve_acl = False
    self.compute_file_checksums = False
    self.dryrun = False
    self.exclude_pattern = None
    self.skip_unsupported_objects = False
    # self.recursion_requested is initialized in command.py (so it can be
    # checked in parent class for all commands).

    if self.sub_opts:
      for o, a in self.sub_opts:
        if o == '-c':
          self.compute_file_checksums = True
        # Note: In gsutil cp command this is specified using -c but here we use
        # -C so we can use -c for checksum arg (to be consistent with Unix rsync
        # command options).
        elif o == '-C':
          self.continue_on_error = True
        elif o == '-d':
          self.delete_extras = True
        elif o == '-e':
          self.exclude_symlinks = True
        elif o == '-n':
          self.dryrun = True
        elif o == '-p':
          preserve_acl = True
        elif o == '-r' or o == '-R':
          self.recursion_requested = True
        elif o == '-U':
          self.skip_unsupported_objects = True
        elif o == '-x':
          if not a:
            raise CommandException('Invalid blank exclude filter')
          try:
            self.exclude_pattern = re.compile(a)
          except re.error:
            raise CommandException('Invalid exclude filter (%s)' % a)
    return CreateCopyHelperOpts(
        preserve_acl=preserve_acl,
        skip_unsupported_objects=self.skip_unsupported_objects)
