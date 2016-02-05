# -*- coding: utf-8 -*-
# Copyright 2012 Google Inc. All Rights Reserved.
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
"""Name expansion iterator and result classes.

Name expansion support for the various ways gsutil lets users refer to
collections of data (via explicit wildcarding as well as directory,
bucket, and bucket subdir implicit wildcarding). This class encapsulates
the various rules for determining how these expansions are done.
"""

# Disable warnings for NameExpansionIteratorQueue functions; they implement
# an interface which does not follow lint guidelines.
# pylint: disable=invalid-name

from __future__ import absolute_import

import os
import sys

import gslib
from gslib.exception import CommandException
from gslib.plurality_checkable_iterator import PluralityCheckableIterator
import gslib.wildcard_iterator
from gslib.wildcard_iterator import StorageUrlFromString


class NameExpansionResult(object):
  """Holds one fully expanded result from iterating over NameExpansionIterator.

  The member data in this class need to be pickleable because
  NameExpansionResult instances are passed through Multiprocessing.Queue. In
  particular, don't include any boto state like StorageUri, since that pulls
  in a big tree of objects, some of which aren't pickleable (and even if
  they were, pickling/unpickling such a large object tree would result in
  significant overhead).

  The state held in this object is needed for handling the various naming cases
  (e.g., copying from a single source URL to a directory generates different
  dest URL names than copying multiple URLs to a directory, to be consistent
  with naming rules used by the Unix cp command). For more details see comments
  in _NameExpansionIterator.
  """

  def __init__(self, source_storage_url, is_multi_source_request,
               names_container, expanded_storage_url):
    """Instantiates a result from name expansion.

    Args:
      source_storage_url: StorageUrl that was being expanded.
      is_multi_source_request: bool indicator whether src_url_str expanded to
          more than one BucketListingRef.
      names_container: Bool indicator whether src_url names a container.
      expanded_storage_url: StorageUrl that was expanded.
    """
    self.source_storage_url = source_storage_url
    self.is_multi_source_request = is_multi_source_request
    self.names_container = names_container
    self.expanded_storage_url = expanded_storage_url

  def __repr__(self):
    return '%s' % self.expanded_storage_url


class _NameExpansionIterator(object):
  """Class that iterates over all source URLs passed to the iterator.

  See details in __iter__ function doc.
  """

  def __init__(self, command_name, debug, logger, gsutil_api, url_strs,
               recursion_requested, all_versions=False,
               cmd_supports_recursion=True, project_id=None,
               continue_on_error=False):
    """Creates a NameExpansionIterator.

    Args:
      command_name: name of command being run.
      debug: Debug level to pass to underlying iterators (range 0..3).
      logger: logging.Logger object.
      gsutil_api: Cloud storage interface.  Settable for testing/mocking.
      url_strs: PluralityCheckableIterator of URL strings needing expansion.
      recursion_requested: True if -r specified on command-line.  If so,
          listings will be flattened so mapped-to results contain objects
          spanning subdirectories.
      all_versions: Bool indicating whether to iterate over all object versions.
      cmd_supports_recursion: Bool indicating whether this command supports a
          '-r' flag. Useful for printing helpful error messages.
      project_id: Project id to use for bucket retrieval.
      continue_on_error: If true, yield no-match exceptions encountered during
                         iteration instead of raising them.

    Examples of _NameExpansionIterator with recursion_requested=True:
      - Calling with one of the url_strs being 'gs://bucket' will enumerate all
        top-level objects, as will 'gs://bucket/' and 'gs://bucket/*'.
      - 'gs://bucket/**' will enumerate all objects in the bucket.
      - 'gs://bucket/abc' will enumerate either the single object abc or, if
         abc is a subdirectory, all objects under abc and any of its
         subdirectories.
      - 'gs://bucket/abc/**' will enumerate all objects under abc or any of its
        subdirectories.
      - 'file:///tmp' will enumerate all files under /tmp, as will
        'file:///tmp/*'
      - 'file:///tmp/**' will enumerate all files under /tmp or any of its
        subdirectories.

    Example if recursion_requested=False:
      calling with gs://bucket/abc/* lists matching objects
      or subdirs, but not sub-subdirs or objects beneath subdirs.

    Note: In step-by-step comments below we give examples assuming there's a
    gs://bucket with object paths:
      abcd/o1.txt
      abcd/o2.txt
      xyz/o1.txt
      xyz/o2.txt
    and a directory file://dir with file paths:
      dir/a.txt
      dir/b.txt
      dir/c/
    """
    self.command_name = command_name
    self.debug = debug
    self.logger = logger
    self.gsutil_api = gsutil_api
    self.url_strs = url_strs
    self.recursion_requested = recursion_requested
    self.all_versions = all_versions
    # Check self.url_strs.HasPlurality() at start because its value can change
    # if url_strs is itself an iterator.
    self.url_strs.has_plurality = self.url_strs.HasPlurality()
    self.cmd_supports_recursion = cmd_supports_recursion
    self.project_id = project_id
    self.continue_on_error = continue_on_error

    # Map holding wildcard strings to use for flat vs subdir-by-subdir listings.
    # (A flat listing means show all objects expanded all the way down.)
    self._flatness_wildcard = {True: '**', False: '*'}

  def __iter__(self):
    """Iterates over all source URLs passed to the iterator.

    For each src url, expands wildcards, object-less bucket names,
    subdir bucket names, and directory names, and generates a flat listing of
    all the matching objects/files.

    You should instantiate this object using the static factory function
    NameExpansionIterator, because consumers of this iterator need the
    PluralityCheckableIterator wrapper built by that function.

    Yields:
      gslib.name_expansion.NameExpansionResult.

    Raises:
      CommandException: if errors encountered.
    """
    for url_str in self.url_strs:
      storage_url = StorageUrlFromString(url_str)

      if storage_url.IsFileUrl() and storage_url.IsStream():
        if self.url_strs.has_plurality:
          raise CommandException('Multiple URL strings are not supported '
                                 'with streaming ("-") URLs.')
        yield NameExpansionResult(storage_url, False, False, storage_url)
        continue

      # Step 1: Expand any explicitly specified wildcards. The output from this
      # step is an iterator of BucketListingRef.
      # Starting with gs://buck*/abc* this step would expand to gs://bucket/abcd

      src_names_bucket = False
      if (storage_url.IsCloudUrl() and storage_url.IsBucket()
          and not self.recursion_requested):
        # UNIX commands like rm and cp will omit directory references.
        # If url_str refers only to buckets and we are not recursing,
        # then produce references of type BUCKET, because they are guaranteed
        # to pass through Step 2 and be omitted in Step 3.
        post_step1_iter = PluralityCheckableIterator(
            self.WildcardIterator(url_str).IterBuckets(
                bucket_fields=['id']))
      else:
        # Get a list of objects and prefixes, expanding the top level for
        # any listed buckets.  If our source is a bucket, however, we need
        # to treat all of the top level expansions as names_container=True.
        post_step1_iter = PluralityCheckableIterator(
            self.WildcardIterator(url_str).IterAll(
                bucket_listing_fields=['name'],
                expand_top_level_buckets=True))
        if storage_url.IsCloudUrl() and storage_url.IsBucket():
          src_names_bucket = True

      # Step 2: Expand bucket subdirs. The output from this
      # step is an iterator of (names_container, BucketListingRef).
      # Starting with gs://bucket/abcd this step would expand to:
      #   iter([(True, abcd/o1.txt), (True, abcd/o2.txt)]).
      subdir_exp_wildcard = self._flatness_wildcard[self.recursion_requested]
      if self.recursion_requested:
        post_step2_iter = _ImplicitBucketSubdirIterator(
            self, post_step1_iter, subdir_exp_wildcard)
      else:
        post_step2_iter = _NonContainerTuplifyIterator(post_step1_iter)
      post_step2_iter = PluralityCheckableIterator(post_step2_iter)

      # Because we actually perform and check object listings here, this will
      # raise if url_args includes a non-existent object.  However,
      # plurality_checkable_iterator will buffer the exception for us, not
      # raising it until the iterator is actually asked to yield the first
      # result.
      if post_step2_iter.IsEmpty():
        if self.continue_on_error:
          try:
            raise CommandException('No URLs matched: %s' % url_str)
          except CommandException, e:
            # Yield a specialized tuple of (exception, stack_trace) to
            # the wrapping PluralityCheckableIterator.
            yield (e, sys.exc_info()[2])
        else:
          raise CommandException('No URLs matched: %s' % url_str)

      # Step 3. Omit any directories, buckets, or bucket subdirectories for
      # non-recursive expansions.
      post_step3_iter = PluralityCheckableIterator(_OmitNonRecursiveIterator(
          post_step2_iter, self.recursion_requested, self.command_name,
          self.cmd_supports_recursion, self.logger))

      src_url_expands_to_multi = post_step3_iter.HasPlurality()
      is_multi_source_request = (self.url_strs.has_plurality
                                 or src_url_expands_to_multi)

      # Step 4. Expand directories and buckets. This step yields the iterated
      # values. Starting with gs://bucket this step would expand to:
      #  [abcd/o1.txt, abcd/o2.txt, xyz/o1.txt, xyz/o2.txt]
      # Starting with file://dir this step would expand to:
      #  [dir/a.txt, dir/b.txt, dir/c/]
      for (names_container, blr) in post_step3_iter:
        src_names_container = src_names_bucket or names_container

        if blr.IsObject():
          yield NameExpansionResult(
              storage_url, is_multi_source_request, src_names_container,
              blr.storage_url)
        else:
          # Use implicit wildcarding to do the enumeration.
          # At this point we are guaranteed that:
          # - Recursion has been requested because non-object entries are
          #   filtered in step 3 otherwise.
          # - This is a prefix or bucket subdirectory because only
          #   non-recursive iterations product bucket references.
          expanded_url = StorageUrlFromString(blr.url_string)
          if expanded_url.IsFileUrl():
            # Convert dir to implicit recursive wildcard.
            url_to_iterate = '%s%s%s' % (blr, os.sep, subdir_exp_wildcard)
          else:
            # Convert subdir to implicit recursive wildcard.
            url_to_iterate = expanded_url.CreatePrefixUrl(
                wildcard_suffix=subdir_exp_wildcard)

          wc_iter = PluralityCheckableIterator(
              self.WildcardIterator(url_to_iterate).IterObjects(
                  bucket_listing_fields=['name']))
          src_url_expands_to_multi = (src_url_expands_to_multi
                                      or wc_iter.HasPlurality())
          is_multi_source_request = (self.url_strs.has_plurality
                                     or src_url_expands_to_multi)
          # This will be a flattened listing of all underlying objects in the
          # subdir.
          for blr in wc_iter:
            yield NameExpansionResult(
                storage_url, is_multi_source_request, True, blr.storage_url)

  def WildcardIterator(self, url_string):
    """Helper to instantiate gslib.WildcardIterator.

    Args are same as gslib.WildcardIterator interface, but this method fills
    in most of the values from instance state.

    Args:
      url_string: URL string naming wildcard objects to iterate.

    Returns:
      Wildcard iterator over URL string.
    """
    return gslib.wildcard_iterator.CreateWildcardIterator(
        url_string, self.gsutil_api, debug=self.debug,
        all_versions=self.all_versions,
        project_id=self.project_id)


def NameExpansionIterator(command_name, debug, logger, gsutil_api, url_strs,
                          recursion_requested, all_versions=False,
                          cmd_supports_recursion=True, project_id=None,
                          continue_on_error=False):
  """Static factory function for instantiating _NameExpansionIterator.

  This wraps the resulting iterator in a PluralityCheckableIterator and checks
  that it is non-empty. Also, allows url_strs to be either an array or an
  iterator.

  Args:
    command_name: name of command being run.
    debug: Debug level to pass to underlying iterators (range 0..3).
    logger: logging.Logger object.
    gsutil_api: Cloud storage interface.  Settable for testing/mocking.
    url_strs: Iterable URL strings needing expansion.
    recursion_requested: True if -r specified on command-line.  If so,
        listings will be flattened so mapped-to results contain objects
        spanning subdirectories.
    all_versions: Bool indicating whether to iterate over all object versions.
    cmd_supports_recursion: Bool indicating whether this command supports a '-r'
        flag. Useful for printing helpful error messages.
    project_id: Project id to use for the current command.
    continue_on_error: If true, yield no-match exceptions encountered during
                       iteration instead of raising them.

  Raises:
    CommandException if underlying iterator is empty.

  Returns:
    Name expansion iterator instance.

  For example semantics, see comments in NameExpansionIterator.__init__.
  """
  url_strs = PluralityCheckableIterator(url_strs)
  name_expansion_iterator = _NameExpansionIterator(
      command_name, debug, logger, gsutil_api, url_strs, recursion_requested,
      all_versions=all_versions, cmd_supports_recursion=cmd_supports_recursion,
      project_id=project_id, continue_on_error=continue_on_error)
  name_expansion_iterator = PluralityCheckableIterator(name_expansion_iterator)
  if name_expansion_iterator.IsEmpty():
    raise CommandException('No URLs matched')
  return name_expansion_iterator


class NameExpansionIteratorQueue(object):
  """Wrapper around NameExpansionIterator with Multiprocessing.Queue interface.

  Only a blocking get() function can be called, and the block and timeout
  params on that function are ignored. All other class functions raise
  NotImplementedError.

  This class is thread safe.
  """

  def __init__(self, name_expansion_iterator, final_value):
    self.name_expansion_iterator = name_expansion_iterator
    self.final_value = final_value
    self.lock = gslib.util.manager.Lock()

  def qsize(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.qsize() not implemented')

  def empty(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.empty() not implemented')

  def full(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.full() not implemented')

  # pylint: disable=unused-argument
  def put(self, obj=None, block=None, timeout=None):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.put() not implemented')

  def put_nowait(self, obj):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.put_nowait() not implemented')

  # pylint: disable=unused-argument
  def get(self, block=None, timeout=None):
    self.lock.acquire()
    try:
      if self.name_expansion_iterator.IsEmpty():
        return self.final_value
      return self.name_expansion_iterator.next()
    finally:
      self.lock.release()

  def get_nowait(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.get_nowait() not implemented')

  def get_no_wait(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.get_no_wait() not implemented')

  def close(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.close() not implemented')

  def join_thread(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.join_thread() not implemented')

  def cancel_join_thread(self):
    raise NotImplementedError(
        'NameExpansionIteratorQueue.cancel_join_thread() not implemented')


class _NonContainerTuplifyIterator(object):
  """Iterator that produces the tuple (False, blr) for each iterated value.

  Used for cases where blr_iter iterates over a set of
  BucketListingRefs known not to name containers.
  """

  def __init__(self, blr_iter):
    """Instantiates iterator.

    Args:
      blr_iter: iterator of BucketListingRef.
    """
    self.blr_iter = blr_iter

  def __iter__(self):
    for blr in self.blr_iter:
      yield (False, blr)


class _OmitNonRecursiveIterator(object):
  """Iterator wrapper for that omits certain values for non-recursive requests.

  This iterates over tuples of (names_container, BucketListingReference) and
  omits directories, prefixes, and buckets from non-recurisve requests
  so that we can properly calculate whether the source URL expands to multiple
  URLs.

  For example, if we have a bucket containing two objects: bucket/foo and
  bucket/foo/bar and we do a non-recursive iteration, only bucket/foo will be
  yielded.
  """

  def __init__(self, tuple_iter, recursion_requested, command_name,
               cmd_supports_recursion, logger):
    """Instanties the iterator.

    Args:
      tuple_iter: Iterator over names_container, BucketListingReference
                  from step 2 in the NameExpansionIterator
      recursion_requested: If false, omit buckets, dirs, and subdirs
      command_name: Command name for user messages
      cmd_supports_recursion: Command recursion support for user messages
      logger: Log object for user messages
    """
    self.tuple_iter = tuple_iter
    self.recursion_requested = recursion_requested
    self.command_name = command_name
    self.cmd_supports_recursion = cmd_supports_recursion
    self.logger = logger

  def __iter__(self):
    for (names_container, blr) in self.tuple_iter:
      if not self.recursion_requested and not blr.IsObject():
        # At this point we either have a bucket or a prefix,
        # so if recursion is not requested, we're going to omit it.
        expanded_url = StorageUrlFromString(blr.url_string)
        if expanded_url.IsFileUrl():
          desc = 'directory'
        else:
          desc = blr.type_name
        if self.cmd_supports_recursion:
          self.logger.info(
              'Omitting %s "%s". (Did you mean to do %s -r?)',
              desc, blr.url_string, self.command_name)
        else:
          self.logger.info('Omitting %s "%s".', desc, blr.url_string)
      else:
        yield (names_container, blr)


class _ImplicitBucketSubdirIterator(object):
  """Iterator wrapper that performs implicit bucket subdir expansion.

  Each iteration yields tuple (names_container, expanded BucketListingRefs)
    where names_container is true if URL names a directory, bucket,
    or bucket subdir.

  For example, iterating over [BucketListingRef("gs://abc")] would expand to:
    [BucketListingRef("gs://abc/o1"), BucketListingRef("gs://abc/o2")]
  if those subdir objects exist, and [BucketListingRef("gs://abc") otherwise.
  """

  def __init__(self, name_exp_instance, blr_iter, subdir_exp_wildcard):
    """Instantiates the iterator.

    Args:
      name_exp_instance: calling instance of NameExpansion class.
      blr_iter: iterator over BucketListingRef prefixes and objects.
      subdir_exp_wildcard: wildcard for expanding subdirectories;
          expected values are ** if the mapped-to results should contain
          objects spanning subdirectories, or * if only one level should
          be listed.
    """
    self.blr_iter = blr_iter
    self.name_exp_instance = name_exp_instance
    self.subdir_exp_wildcard = subdir_exp_wildcard

  def __iter__(self):
    for blr in self.blr_iter:
      if blr.IsPrefix():
        # This is a bucket subdirectory, list objects according to the wildcard.
        prefix_url = StorageUrlFromString(blr.url_string).CreatePrefixUrl(
            wildcard_suffix=self.subdir_exp_wildcard)
        implicit_subdir_iterator = PluralityCheckableIterator(
            self.name_exp_instance.WildcardIterator(
                prefix_url).IterAll(bucket_listing_fields=['name']))
        if not implicit_subdir_iterator.IsEmpty():
          for exp_blr in implicit_subdir_iterator:
            yield (True, exp_blr)
        else:
          # Prefix that contains no objects, for example in the $folder$ case
          # or an empty filesystem directory.
          yield (False, blr)
      elif blr.IsObject():
        yield (False, blr)
      else:
        raise CommandException(
            '_ImplicitBucketSubdirIterator got a bucket reference %s' % blr)
