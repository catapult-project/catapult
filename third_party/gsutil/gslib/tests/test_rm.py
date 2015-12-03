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
"""Integration tests for rm command."""

from __future__ import absolute_import

import re

import gslib.tests.testcase as testcase
from gslib.tests.testcase.base import MAX_BUCKET_LENGTH
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.util import GenerationFromURI as urigen
from gslib.tests.util import ObjectToURI as suri
from gslib.util import Retry


class TestRm(testcase.GsUtilIntegrationTestCase):
  """Integration tests for rm command."""

  def _RunRemoveCommandAndCheck(self, command_and_args, objects_to_remove=None,
                                buckets_to_remove=None, stdin=None):
    """Tests a remove command in the presence of eventual listing consistency.

    Eventual listing consistency means that a remove command may not see all
    of the objects to be removed at once. When removing multiple objects
    (or buckets via -r), some calls may return no matches and multiple calls
    to the rm command may be necessary to reach the desired state. This function
    retries the rm command, incrementally tracking what has been removed and
    ensuring that the exact set of objects/buckets are removed across all
    retried calls.

    The caller is responsible for confirming the existence of buckets/objects
    prior to calling this function.

    Args:
      command_and_args: List of strings representing the rm command+args to run.
      objects_to_remove: List of object URL strings (optionally including
          generation) that should be removed by the command, if any.
      buckets_to_remove: List of bucket URL strings that should be removed by
         the command, if any.
      stdin: String of data to pipe to the process as standard input (for
         testing -I option).
    """
    cumulative_stderr_lines = set()
    bucket_strings = []
    for bucket_to_remove in buckets_to_remove or []:
      bucket_strings.append('Removing %s/...' % bucket_to_remove)
    object_strings = []
    for object_to_remove in objects_to_remove or []:
      object_strings.append('Removing %s...' % object_to_remove)
    expected_stderr_lines = set(object_strings + bucket_strings)

    @Retry(AssertionError, tries=5, timeout_secs=1)
    def _RunRmCommandAndCheck():
      """Runs the command with retries, updating+checking cumulative output."""
      stderr = self.RunGsUtil(command_and_args, return_stderr=True,
                              expected_status=None, stdin=stdin)
      update_lines = True
      # Retry 404's and 409's due to eventual listing consistency, but don't add
      # the output to the set.
      if ('No URLs matched' in stderr or
          '409 BucketNotEmpty' in stderr or
          '409 VersionedBucketNotEmpty' in stderr):
        update_lines = False

      # For recursive deletes of buckets, it is possible that the bucket is
      # deleted before the objects are all present in the listing, in which case
      # we will never see all of the expected "Removing object..." messages.
      # Since this is still a successful outcome, just return successfully.
      if '-r' in command_and_args and 'bucket does not exist' in stderr:
        for bucket_to_remove in buckets_to_remove:
          matching_bucket = re.match(r'.*404\s+%s\s+bucket does not exist' %
                                     re.escape(bucket_to_remove), stderr)
          if matching_bucket:
            for line in cumulative_stderr_lines:
              if 'Removing %s/...' % bucket_to_remove in line:
                return
            if 'Removing %s/...' % bucket_to_remove in stderr:
              return

      if update_lines:
        cumulative_stderr_lines.update(set(stderr.splitlines()))

      # Ensure all of the expected strings are present.
      self.assertEqual(cumulative_stderr_lines, expected_stderr_lines)

    _RunRmCommandAndCheck()

  def test_all_versions_current(self):
    """Test that 'rm -a' for an object with a current version works."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('foo')
    key_uri.set_contents_from_string('bar')
    g1 = urigen(key_uri)
    key_uri.set_contents_from_string('baz')
    g2 = urigen(key_uri)
    self.AssertNObjectsInBucket(bucket_uri, 2, versioned=True)
    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1(stderr_lines):
      stderr = self.RunGsUtil(['-m', 'rm', '-a', suri(key_uri)],
                              return_stderr=True)
      stderr_lines.update(set(stderr.splitlines()))
      stderr = '\n'.join(stderr_lines)
      self.assertEqual(stderr.count('Removing %s://' % self.default_provider),
                       2)
      self.assertIn('Removing %s#%s...' % (suri(key_uri), g1), stderr)
      self.assertIn('Removing %s#%s...' % (suri(key_uri), g2), stderr)
    all_stderr_lines = set()
    _Check1(all_stderr_lines)
    self.AssertNObjectsInBucket(bucket_uri, 0, versioned=True)

  def test_all_versions_no_current(self):
    """Test that 'rm -a' for an object without a current version works."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('foo')
    key_uri.set_contents_from_string('bar')
    g1 = urigen(key_uri)
    key_uri.set_contents_from_string('baz')
    g2 = urigen(key_uri)
    self._RunRemoveCommandAndCheck(
        ['-m', 'rm', '-a', suri(key_uri)],
        objects_to_remove=['%s#%s' % (suri(key_uri), g1),
                           '%s#%s' % (suri(key_uri), g2)])
    self.AssertNObjectsInBucket(bucket_uri, 0, versioned=True)

  def test_fails_for_missing_obj(self):
    bucket_uri = self.CreateVersionedBucket()
    stderr = self.RunGsUtil(['rm', '-a', '%s' % suri(bucket_uri, 'foo')],
                            return_stderr=True, expected_status=1)
    self.assertIn('No URLs matched', stderr)

  def test_remove_all_versions_recursive_on_bucket(self):
    """Test that 'rm -r' works on bucket."""
    bucket_uri = self.CreateVersionedBucket()
    k1_uri = bucket_uri.clone_replace_name('foo')
    k2_uri = bucket_uri.clone_replace_name('foo2')
    k1_uri.set_contents_from_string('bar')
    k2_uri.set_contents_from_string('bar2')
    k1g1 = urigen(k1_uri)
    k2g1 = urigen(k2_uri)
    k1_uri.set_contents_from_string('baz')
    k2_uri.set_contents_from_string('baz2')
    k1g2 = urigen(k1_uri)
    k2g2 = urigen(k2_uri)

    self.AssertNObjectsInBucket(bucket_uri, 4, versioned=True)

    self._RunRemoveCommandAndCheck(
        ['rm', '-r', suri(bucket_uri)],
        objects_to_remove=['%s#%s' % (suri(k1_uri), k1g1),
                           '%s#%s' % (suri(k1_uri), k1g2),
                           '%s#%s' % (suri(k2_uri), k2g1),
                           '%s#%s' % (suri(k2_uri), k2g2)],
        buckets_to_remove=[suri(bucket_uri)])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check():
      # Bucket should no longer exist.
      stderr = self.RunGsUtil(['ls', '-a', suri(bucket_uri)],
                              return_stderr=True, expected_status=1)
      self.assertIn('bucket does not exist', stderr)
    _Check()

  def test_remove_all_versions_recursive_on_subdir(self):
    """Test that 'rm -r' works on subdir."""
    bucket_uri = self.CreateVersionedBucket()
    k1_uri = bucket_uri.clone_replace_name('dir/foo')
    k2_uri = bucket_uri.clone_replace_name('dir/foo2')
    k1_uri.set_contents_from_string('bar')
    k2_uri.set_contents_from_string('bar2')
    k1g1 = urigen(k1_uri)
    k2g1 = urigen(k2_uri)
    k1_uri.set_contents_from_string('baz')
    k2_uri.set_contents_from_string('baz2')
    k1g2 = urigen(k1_uri)
    k2g2 = urigen(k2_uri)

    self.AssertNObjectsInBucket(bucket_uri, 4, versioned=True)

    self._RunRemoveCommandAndCheck(
        ['rm', '-r', '%s' % suri(bucket_uri, 'dir')],
        objects_to_remove=['%s#%s' % (suri(k1_uri), k1g1),
                           '%s#%s' % (suri(k1_uri), k1g2),
                           '%s#%s' % (suri(k2_uri), k2g1),
                           '%s#%s' % (suri(k2_uri), k2g2)])
    self.AssertNObjectsInBucket(bucket_uri, 0, versioned=True)

  def test_missing_first_force(self):
    bucket_uri = self.CreateBucket()
    object_uri = self.CreateObject(bucket_uri=bucket_uri, object_name='present',
                                   contents='foo')
    self.AssertNObjectsInBucket(bucket_uri, 1)
    self.RunGsUtil(['rm', '%s' % suri(bucket_uri, 'missing'),
                    suri(object_uri)], expected_status=1)
    stderr = self.RunGsUtil(
        ['rm', '-f', '%s' % suri(bucket_uri, 'missing'), suri(object_uri)],
        return_stderr=True, expected_status=1)
    self.assertEqual(stderr.count('Removing %s://' % self.default_provider), 1)
    self.RunGsUtil(['stat', suri(object_uri)], expected_status=1)

  def test_some_missing(self):
    """Test that 'rm -a' fails when some but not all uris don't exist."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('foo')
    key_uri.set_contents_from_string('bar')
    self.AssertNObjectsInBucket(bucket_uri, 1, versioned=True)
    stderr = self.RunGsUtil(['rm', '-a', suri(key_uri),
                             '%s' % suri(bucket_uri, 'missing')],
                            return_stderr=True, expected_status=1)
    self.assertEqual(stderr.count('Removing %s://' % self.default_provider), 1)
    self.assertIn('No URLs matched', stderr)

  def test_some_missing_force(self):
    """Test that 'rm -af' succeeds despite hidden first uri."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('foo')
    key_uri.set_contents_from_string('bar')
    self.AssertNObjectsInBucket(bucket_uri, 1, versioned=True)
    stderr = self.RunGsUtil(
        ['rm', '-af', suri(key_uri), '%s' % suri(bucket_uri, 'missing')],
        return_stderr=True, expected_status=1)
    self.assertEqual(stderr.count('Removing %s://' % self.default_provider), 1)
    self.AssertNObjectsInBucket(bucket_uri, 0)

  def test_folder_objects_deleted(self):
    """Test for 'rm -r' of a folder with a dir_$folder$ marker."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('abc/o1')
    key_uri.set_contents_from_string('foobar')
    folder_uri = bucket_uri.clone_replace_name('abc_$folder$')
    folder_uri.set_contents_from_string('')
    self.AssertNObjectsInBucket(bucket_uri, 2, versioned=True)
    # This could fail due to eventual listing consistency, so use retry and
    # expected_status=None to guard against No URLs matched exceptions.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _RemoveAndCheck():
      self.RunGsUtil(['rm', '-r', '%s' % suri(bucket_uri, 'abc')],
                     expected_status=None)
      self.AssertNObjectsInBucket(bucket_uri, 0, versioned=True)
    _RemoveAndCheck()
    # Bucket should not be deleted (Should not get ServiceException).
    bucket_uri.get_location(validate=False)

  def test_folder_objects_deleted_with_wildcard(self):
    """Test for 'rm -r' of a folder with a dir_$folder$ marker."""
    bucket_uri = self.CreateVersionedBucket()
    key_uri = bucket_uri.clone_replace_name('abc/o1')
    key_uri.set_contents_from_string('foobar')
    folder_uri = bucket_uri.clone_replace_name('abc_$folder$')
    folder_uri.set_contents_from_string('')

    self.AssertNObjectsInBucket(bucket_uri, 2, versioned=True)
    self._RunRemoveCommandAndCheck(
        ['rm', '-r', '%s' % suri(bucket_uri, '**')],
        objects_to_remove=['%s#%s' % (suri(key_uri), urigen(key_uri)),
                           '%s#%s' % (suri(folder_uri), urigen(folder_uri))])
    self.AssertNObjectsInBucket(bucket_uri, 0, versioned=True)
    # Bucket should not be deleted (Should not get ServiceException).
    bucket_uri.get_location(validate=False)

  @SkipForS3('Listing/removing S3 DeleteMarkers is not supported')
  def test_recursive_bucket_rm(self):
    """Test for 'rm -r' of a bucket."""
    bucket_uri = self.CreateBucket()
    object_uri = self.CreateObject(bucket_uri, contents='foo')
    self.AssertNObjectsInBucket(bucket_uri, 1)
    self._RunRemoveCommandAndCheck(
        ['rm', '-r', suri(bucket_uri)],
        objects_to_remove=['%s#%s' % (suri(object_uri), urigen(object_uri))],
        buckets_to_remove=[suri(bucket_uri)])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      # Bucket should be deleted.
      stderr = self.RunGsUtil(['ls', '-Lb', suri(bucket_uri)],
                              return_stderr=True, expected_status=1)
      self.assertIn('bucket does not exist', stderr)
    _Check1()

    # Now try same thing, but for a versioned bucket with multiple versions of
    # an object present.
    bucket_uri = self.CreateVersionedBucket()
    self.CreateObject(bucket_uri, 'obj', 'z')
    self.CreateObject(bucket_uri, 'obj', 'z')
    final_uri = self.CreateObject(bucket_uri, 'obj', 'z')
    self.AssertNObjectsInBucket(bucket_uri, 3, versioned=True)
    self._RunRemoveCommandAndCheck(['rm', suri(bucket_uri, '**')],
                                   objects_to_remove=['%s' % final_uri])

    stderr = self.RunGsUtil(['rb', suri(bucket_uri)],
                            return_stderr=True, expected_status=1)
    self.assertIn('Bucket is not empty', stderr)

    # Now try with rm -r.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      self.RunGsUtil(['rm', '-r', suri(bucket_uri)])
      # Bucket should be deleted.
      stderr = self.RunGsUtil(['ls', '-Lb', suri(bucket_uri)],
                              return_stderr=True, expected_status=1)
      self.assertIn('bucket does not exist', stderr)
    _Check2()

  def test_recursive_bucket_rm_with_wildcarding(self):
    """Tests removing all objects and buckets matching a bucket wildcard."""
    buri_base = 'gsutil-test-%s' % self.GetTestMethodName()
    buri_base = buri_base[:MAX_BUCKET_LENGTH-20]
    buri_base = '%s-%s' % (buri_base, self.MakeRandomTestString())
    buri1 = self.CreateBucket(bucket_name='%s-tbuck1' % buri_base)
    buri2 = self.CreateBucket(bucket_name='%s-tbuck2' % buri_base)
    buri3 = self.CreateBucket(bucket_name='%s-tb3' % buri_base)
    ouri1 = self.CreateObject(bucket_uri=buri1, object_name='o1', contents='z')
    ouri2 = self.CreateObject(bucket_uri=buri2, object_name='o2', contents='z')
    self.CreateObject(bucket_uri=buri3, object_name='o3', contents='z')

    self.AssertNObjectsInBucket(buri1, 1)
    self.AssertNObjectsInBucket(buri2, 1)
    self.AssertNObjectsInBucket(buri3, 1)

    self._RunRemoveCommandAndCheck(
        ['rm', '-r', '%s://%s-tbu*' % (self.default_provider, buri_base)],
        objects_to_remove=['%s#%s' % (suri(ouri1), urigen(ouri1)),
                           '%s#%s' % (suri(ouri2), urigen(ouri2))],
        buckets_to_remove=[suri(buri1), suri(buri2)])

    self.AssertNObjectsInBucket(buri3, 1)

  def test_rm_quiet(self):
    """Test that 'rm -q' outputs no progress indications."""
    bucket_uri = self.CreateBucket()
    key_uri = self.CreateObject(bucket_uri=bucket_uri, contents='foo')
    self.AssertNObjectsInBucket(bucket_uri, 1)
    self._RunRemoveCommandAndCheck(['-q', 'rm', suri(key_uri)], [])
    self.AssertNObjectsInBucket(bucket_uri, 0)

  def test_rm_object_with_slash(self):
    """Tests removing a bucket that has an object with a slash in it."""
    bucket_uri = self.CreateVersionedBucket()
    ouri1 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='/dirwithslash/foo', contents='z')
    ouri2 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='dirnoslash/foo', contents='z')
    ouri3 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='dirnoslash/foo2', contents='z')

    self.AssertNObjectsInBucket(bucket_uri, 3, versioned=True)

    self._RunRemoveCommandAndCheck(
        ['rm', '-r', suri(bucket_uri)],
        objects_to_remove=['%s#%s' % (suri(ouri1), urigen(ouri1)),
                           '%s#%s' % (suri(ouri2), urigen(ouri2)),
                           '%s#%s' % (suri(ouri3), urigen(ouri3))],
        buckets_to_remove=[suri(bucket_uri)])

  def test_slasher_horror_film(self):
    """Tests removing a bucket with objects that are filled with slashes."""
    bucket_uri = self.CreateVersionedBucket()
    ouri1 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='h/e/l//lo',
                              contents='Halloween')
    ouri2 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='/h/e/l/l/o',
                              contents='A Nightmare on Elm Street')
    ouri3 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='//h//e/l//l/o',
                              contents='Friday the 13th')
    ouri4 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='//h//e//l//l//o',
                              contents='I Know What You Did Last Summer')
    ouri5 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='/',
                              contents='Scream')
    ouri6 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='//',
                              contents='Child\'s Play')
    ouri7 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='///',
                              contents='The Prowler')
    ouri8 = self.CreateObject(bucket_uri=bucket_uri,
                              object_name='////',
                              contents='Black Christmas')
    ouri9 = self.CreateObject(
        bucket_uri=bucket_uri,
        object_name='everything/is/better/with/slashes///////',
        contents='Maniac')

    self.AssertNObjectsInBucket(bucket_uri, 9, versioned=True)

    # We add a slash to URIs with a trailing slash,
    # because ObjectToURI (suri) removes one trailing slash.
    objects_to_remove = [
        '%s#%s' % (suri(ouri1), urigen(ouri1)),
        '%s#%s' % (suri(ouri2), urigen(ouri2)),
        '%s#%s' % (suri(ouri3), urigen(ouri3)),
        '%s#%s' % (suri(ouri4), urigen(ouri4)),
        '%s#%s' % (suri(ouri5) + '/', urigen(ouri5)),
        '%s#%s' % (suri(ouri6) + '/', urigen(ouri6)),
        '%s#%s' % (suri(ouri7) + '/', urigen(ouri7)),
        '%s#%s' % (suri(ouri8) + '/', urigen(ouri8)),
        '%s#%s' % (suri(ouri9) + '/', urigen(ouri9))]

    self._RunRemoveCommandAndCheck(['-m', 'rm', '-r', suri(bucket_uri)],
                                   objects_to_remove=objects_to_remove,
                                   buckets_to_remove=[suri(bucket_uri)])

  @SkipForS3('GCS versioning headers not supported by S3')
  def test_rm_failing_precondition(self):
    """Test for '-h x-goog-if-generation-match:value rm' of an object."""
    bucket_uri = self.CreateBucket()
    object_uri = self.CreateObject(bucket_uri, contents='foo')
    stderr = self.RunGsUtil(['-h', 'x-goog-if-generation-match:12345', 'rm',
                             suri(object_uri)], return_stderr=True,
                            expected_status=1)
    self.assertRegexpMatches(
        stderr, r'PreconditionException: 412 Precondition\s*Failed')

  def test_stdin_args(self):
    """Tests rm with the -I option."""
    buri1 = self.CreateVersionedBucket()
    ouri1 = self.CreateObject(bucket_uri=buri1,
                              object_name='foo',
                              contents='foocontents')
    self.CreateObject(bucket_uri=buri1, object_name='bar',
                      contents='barcontents')
    ouri3 = self.CreateObject(bucket_uri=buri1,
                              object_name='baz',
                              contents='bazcontents')
    buri2 = self.CreateVersionedBucket()
    ouri4 = self.CreateObject(bucket_uri=buri2,
                              object_name='moo',
                              contents='moocontents')
    self.AssertNObjectsInBucket(buri1, 3, versioned=True)
    self.AssertNObjectsInBucket(buri2, 1, versioned=True)

    objects_to_remove = ['%s#%s' % (suri(ouri1), urigen(ouri1)),
                         '%s#%s' % (suri(ouri3), urigen(ouri3)),
                         '%s#%s' % (suri(ouri4), urigen(ouri4))]
    stdin = '\n'.join(objects_to_remove)
    self._RunRemoveCommandAndCheck(['rm', '-I'],
                                   objects_to_remove=objects_to_remove,
                                   stdin=stdin)
    self.AssertNObjectsInBucket(buri1, 1, versioned=True)
    self.AssertNObjectsInBucket(buri2, 0, versioned=True)

  def test_rm_nonexistent_bucket_recursive(self):
    stderr = self.RunGsUtil(
        ['rm', '-rf', '%s://%s' % (self.default_provider,
                                   self.nonexistent_bucket_name)],
        return_stderr=True, expected_status=1)
    self.assertIn('Encountered non-existent bucket', stderr)

  def test_rm_multiple_nonexistent_objects(self):
    bucket_uri = self.CreateBucket()
    nonexistent_object1 = suri(bucket_uri, 'nonexistent1')
    nonexistent_object2 = suri(bucket_uri, 'nonexistent1')
    stderr = self.RunGsUtil(
        ['rm', '-rf', nonexistent_object1, nonexistent_object2],
        return_stderr=True, expected_status=1)
    self.assertIn('2 files/objects could not be removed.', stderr)
