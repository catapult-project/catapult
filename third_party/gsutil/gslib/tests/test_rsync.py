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
"""Integration tests for rsync command."""

import os

import crcmod

import gslib.tests.testcase as testcase
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.util import ObjectToURI as suri
from gslib.tests.util import SequentialAndParallelTransfer
from gslib.tests.util import SetBotoConfigForTest
from gslib.tests.util import unittest
from gslib.util import IS_WINDOWS
from gslib.util import Retry
from gslib.util import UsingCrcmodExtension

NO_CHANGES = 'Building synchronization state...\nStarting synchronization\n'


def _TailSet(start_point, listing):
  """Returns set of object name tails.

  Tails can be compared between source and dest, past the point at which rsync
  was done.  For example if test ran rsync gs://bucket1/dir gs://bucket2/dir2,
  the tails for listings from bucket1 would start after "dir", while the tails
  for listings from bucket2 would start after "dir2".

  Args:
    start_point: The target of the rsync command, e.g., for the above command it
                 would be gs://bucket1/dir for the bucket1 listing results and
                 gs://bucket2/dir2 for the bucket2 listing results.
    listing: The listing over which to compute tail.

  Returns:
    Object name tails.
  """
  return set(l[len(start_point):] for l in listing.strip().split('\n'))


# TODO: Add inspection to the retry wrappers in this test suite where the state
# at the end of a retry block is depended upon by subsequent tests (since
# listing content can vary depending on which backend server is reached until
# eventual consistency is reached).
# TODO: Remove retry wrappers and AssertNObjectsInBucket calls if GCS ever
# supports strong listing consistency.
class TestRsync(testcase.GsUtilIntegrationTestCase):
  """Integration tests for rsync command."""

  @staticmethod
  def _FlatListDir(directory):
    """Perform a flat listing over directory.

    Args:
      directory: The directory to list

    Returns:
      Listings with path separators canonicalized to '/', to make assertions
      easier for Linux vs Windows.
    """
    result = []
    for dirpath, _, filenames in os.walk(directory):
      for f in filenames:
        result.append(os.path.join(dirpath, f))
    return '\n'.join(result).replace('\\', '/')

  def _FlatListBucket(self, bucket_url_string):
    """Perform a flat listing over bucket_url_string."""
    return self.RunGsUtil(['ls', suri(bucket_url_string, '**')],
                          return_stdout=True)

  def test_invalid_args(self):
    """Tests various invalid argument cases."""
    bucket_uri = self.CreateBucket()
    obj1 = self.CreateObject(bucket_uri=bucket_uri, object_name='obj1',
                             contents='obj1')
    tmpdir = self.CreateTempDir()
    # rsync object to bucket.
    self.RunGsUtil(['rsync', suri(obj1), suri(bucket_uri)], expected_status=1)
    # rsync bucket to object.
    self.RunGsUtil(['rsync', suri(bucket_uri), suri(obj1)], expected_status=1)
    # rsync bucket to non-existent bucket.
    self.RunGsUtil(['rsync', suri(bucket_uri), self.nonexistent_bucket_name],
                   expected_status=1)
    # rsync object to dir.
    self.RunGsUtil(['rsync', suri(obj1), tmpdir], expected_status=1)
    # rsync dir to object.
    self.RunGsUtil(['rsync', tmpdir, suri(obj1)], expected_status=1)
    # rsync dir to non-existent bucket.
    self.RunGsUtil(['rsync', tmpdir, suri(obj1), self.nonexistent_bucket_name],
                   expected_status=1)

  # Note: The tests below exercise the cases
  # {src_dir, src_bucket} X {dst_dir, dst_bucket}. We use gsutil rsync -d for
  # all the cases but then have just one test without -d (test_bucket_to_bucket)
  # as representative of handling without the -d option. This provides
  # reasonable test coverage because the -d handling it src/dest URI-type
  # independent, and keeps the test case combinations more manageable.

  def test_bucket_to_bucket(self):
    """Tests that flat and recursive rsync between 2 buckets works correctly."""
    # Create 2 buckets with 1 overlapping object, 1 extra object at root level
    # in each, and 1 extra object 1 level down in each, where one of the objects
    # starts with "." to test that we don't skip those objects. Make the
    # overlapping objects named the same but with different content, to test
    # that we detect and properly copy in that case.
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='.obj2',
                      contents='.obj2')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='subdir/obj3',
                      contents='subdir/obj3')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='.obj2',
                      contents='.OBJ2')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj4',
                      contents='obj4')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='subdir/obj5',
                      contents='subdir/obj5')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Second bucket should have new objects added from source bucket (without
      # removing extraneeous object found in dest bucket), and without the
      # subdir objects synchronized.
      self.assertEquals(listing2,
                        set(['/obj1', '/.obj2', '/obj4', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were correctly synchronized (bucket to bucket sync uses
      # checksums).
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket1_uri, '.obj2')], return_stdout=True))
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket2_uri, '.obj2')], return_stdout=True))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', suri(bucket1_uri), suri(bucket2_uri)], return_stderr=True))
    _Check2()

    # Now add and remove some objects in each bucket and test rsync -r.
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj6',
                      contents='obj6')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj7',
                      contents='obj7')
    self.RunGsUtil(['rm', suri(bucket1_uri, 'obj1')])
    self.RunGsUtil(['rm', suri(bucket2_uri, '.obj2')])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      self.RunGsUtil(['rsync', '-r', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/.obj2', '/obj6', '/subdir/obj3']))
      # Second bucket should have objects tha were newly added to first bucket
      # (wihout removing extraneous dest bucket objects), and without the
      # subdir objects synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/obj4', '/obj6',
                                       '/obj7', '/subdir/obj3',
                                       '/subdir/obj5']))
    _Check3()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check4():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-r', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check4()

  def test_bucket_to_bucket_minus_d(self):
    """Tests that flat and recursive rsync between 2 buckets works correctly."""
    # Create 2 buckets with 1 overlapping object, 1 extra object at root level
    # in each, and 1 extra object 1 level down in each, where one of the objects
    # starts with "." to test that we don't skip those objects. Make the
    # overlapping objects named the same but with different content, to test
    # that we detect and properly copy in that case.
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='.obj2',
                      contents='.obj2')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='subdir/obj3',
                      contents='subdir/obj3')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='.obj2',
                      contents='.OBJ2')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj4',
                      contents='obj4')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='subdir/obj5',
                      contents='subdir/obj5')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Second bucket should have content like first bucket but without the
      # subdir objects synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were correctly synchronized (bucket to bucket sync uses
      # checksums).
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket1_uri, '.obj2')], return_stdout=True))
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket2_uri, '.obj2')], return_stdout=True))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

    # Now add and remove some objects in each bucket and test rsync -r.
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj6',
                      contents='obj6')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj7',
                      contents='obj7')
    self.RunGsUtil(['rm', suri(bucket1_uri, 'obj1')])
    self.RunGsUtil(['rm', suri(bucket2_uri, '.obj2')])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      self.RunGsUtil(['rsync', '-d', '-r',
                      suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/.obj2', '/obj6', '/subdir/obj3']))
      # Second bucket should have content like first bucket but without the
      # subdir objects synchronized.
      self.assertEquals(listing2, set(['/.obj2', '/obj6', '/subdir/obj3']))
    _Check3()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check4():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-r', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check4()

  # Test sequential upload as well as parallel composite upload case.
  @SequentialAndParallelTransfer
  @unittest.skipUnless(UsingCrcmodExtension(crcmod),
                       'Test requires fast crcmod.')
  def test_dir_to_bucket_minus_d(self):
    """Tests that flat and recursive rsync dir to bucket works correctly."""
    # Create dir and bucket with 1 overlapping object, 1 extra object at root
    # level in each, and 1 extra object 1 level down in each, where one of the
    # objects starts with "." to test that we don't skip those objects. Make the
    # overlapping objects named the same but with different content, to test
    # that we detect and properly copy in that case.
    tmpdir = self.CreateTempDir()
    subdir = os.path.join(tmpdir, 'subdir')
    os.mkdir(subdir)
    bucket_uri = self.CreateBucket()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    self.CreateTempFile(tmpdir=subdir, file_name='obj3', contents='subdir/obj3')
    self.CreateObject(bucket_uri=bucket_uri, object_name='.obj2',
                      contents='.OBJ2')
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj4',
                      contents='obj4')
    self.CreateObject(bucket_uri=bucket_uri, object_name='subdir/obj5',
                      contents='subdir/obj5')

    # Need to make sure the bucket listing is caught-up, otherwise the
    # first rsync may not see .obj2 and overwrite it.
    self.AssertNObjectsInBucket(bucket_uri, 3)

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-d', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Bucket should have content like dir but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were not synchronized (dir to bucket sync doesn't use checksums
      # unless you specify -c).
      with open(os.path.join(tmpdir, '.obj2')) as f:
        self.assertEquals('.obj2', '\n'.join(f.readlines()))
      self.assertEquals('.OBJ2', self.RunGsUtil(
          ['cat', suri(bucket_uri, '.obj2')], return_stdout=True))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', tmpdir, suri(bucket_uri)], return_stderr=True))
    _Check2()

    # Now rerun the sync with the -c option.
    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      """Tests rsync -c works as expected."""
      self.RunGsUtil(['rsync', '-d', '-c', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Bucket should have content like dir but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were synchronized (dir to bucket sync with -c uses checksums).
      with open(os.path.join(tmpdir, '.obj2')) as f:
        self.assertEquals('.obj2', '\n'.join(f.readlines()))
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket_uri, '.obj2')], return_stdout=True))
    _Check3()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check4():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-c', tmpdir, suri(bucket_uri)], return_stderr=True))
    _Check4()

    # Now add and remove some objects in dir and bucket and test rsync -r.
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj6', contents='obj6')
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj7',
                      contents='obj7')
    os.unlink(os.path.join(tmpdir, 'obj1'))
    self.RunGsUtil(['rm', suri(bucket_uri, '.obj2')])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check5():
      self.RunGsUtil(['rsync', '-d', '-r', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/.obj2', '/obj6', '/subdir/obj3']))
      # Bucket should have content like dir but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/.obj2', '/obj6', '/subdir/obj3']))
    _Check5()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check6():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-r', tmpdir, suri(bucket_uri)], return_stderr=True))
    _Check6()

  @unittest.skipUnless(UsingCrcmodExtension(crcmod),
                       'Test requires fast crcmod.')
  def test_dir_to_dir_minus_d(self):
    """Tests that flat and recursive rsync dir to dir works correctly."""
    # Create 2 dirs with 1 overlapping file, 1 extra file at root
    # level in each, and 1 extra file 1 level down in each, where one of the
    # objects starts with "." to test that we don't skip those objects. Make the
    # overlapping files named the same but with different content, to test
    # that we detect and properly copy in that case.
    tmpdir1 = self.CreateTempDir()
    tmpdir2 = self.CreateTempDir()
    subdir1 = os.path.join(tmpdir1, 'subdir1')
    subdir2 = os.path.join(tmpdir2, 'subdir2')
    os.mkdir(subdir1)
    os.mkdir(subdir2)
    self.CreateTempFile(tmpdir=tmpdir1, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir1, file_name='.obj2', contents='.obj2')
    self.CreateTempFile(
        tmpdir=subdir1, file_name='obj3', contents='subdir1/obj3')
    self.CreateTempFile(tmpdir=tmpdir2, file_name='.obj2', contents='.OBJ2')
    self.CreateTempFile(tmpdir=tmpdir2, file_name='obj4', contents='obj4')
    self.CreateTempFile(
        tmpdir=subdir2, file_name='obj5', contents='subdir2/obj5')

    self.RunGsUtil(['rsync', '-d', tmpdir1, tmpdir2])
    listing1 = _TailSet(tmpdir1, self._FlatListDir(tmpdir1))
    listing2 = _TailSet(tmpdir2, self._FlatListDir(tmpdir2))
    # dir1 should have un-altered content.
    self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir1/obj3']))
    # dir2 should have content like dir1 but without the subdir1 objects
    # synchronized.
    self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir2/obj5']))
    # Assert that the src/dest objects that had same length but different
    # checksums were not synchronized (dir to dir sync doesn't use checksums
    # unless you specify -c).
    with open(os.path.join(tmpdir1, '.obj2')) as f:
      self.assertEquals('.obj2', '\n'.join(f.readlines()))
    with open(os.path.join(tmpdir2, '.obj2')) as f:
      self.assertEquals('.OBJ2', '\n'.join(f.readlines()))

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', tmpdir1, tmpdir2], return_stderr=True))
    _Check1()

    # Now rerun the sync with the -c option.
    self.RunGsUtil(['rsync', '-d', '-c', tmpdir1, tmpdir2])
    listing1 = _TailSet(tmpdir1, self._FlatListDir(tmpdir1))
    listing2 = _TailSet(tmpdir2, self._FlatListDir(tmpdir2))
    # dir1 should have un-altered content.
    self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir1/obj3']))
    # dir2 should have content like dir but without the subdir objects
    # synchronized.
    self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir2/obj5']))
    # Assert that the src/dest objects that had same length but different
    # content were synchronized (dir to dir sync with -c uses checksums).
    with open(os.path.join(tmpdir1, '.obj2')) as f:
      self.assertEquals('.obj2', '\n'.join(f.readlines()))
    with open(os.path.join(tmpdir1, '.obj2')) as f:
      self.assertEquals('.obj2', '\n'.join(f.readlines()))

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-c', tmpdir1, tmpdir2], return_stderr=True))
    _Check2()

    # Now add and remove some objects in both dirs and test rsync -r.
    self.CreateTempFile(tmpdir=tmpdir1, file_name='obj6', contents='obj6')
    self.CreateTempFile(tmpdir=tmpdir2, file_name='obj7', contents='obj7')
    os.unlink(os.path.join(tmpdir1, 'obj1'))
    os.unlink(os.path.join(tmpdir2, '.obj2'))

    self.RunGsUtil(['rsync', '-d', '-r', tmpdir1, tmpdir2])
    listing1 = _TailSet(tmpdir1, self._FlatListDir(tmpdir1))
    listing2 = _TailSet(tmpdir2, self._FlatListDir(tmpdir2))
    # dir1 should have un-altered content.
    self.assertEquals(listing1, set(['/.obj2', '/obj6', '/subdir1/obj3']))
    # dir2 should have content like dir but without the subdir objects
    # synchronized.
    self.assertEquals(listing2, set(['/.obj2', '/obj6', '/subdir1/obj3']))

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-r', tmpdir1, tmpdir2], return_stderr=True))
    _Check3()

  def test_dir_to_dir_minus_d_more_files_than_bufsize(self):
    """Tests concurrently building listing from multiple tmp file ranges."""
    # Create 2 dirs, where each dir has 1000 objects and differing names.
    tmpdir1 = self.CreateTempDir()
    tmpdir2 = self.CreateTempDir()
    for i in range(0, 1000):
      self.CreateTempFile(tmpdir=tmpdir1, file_name='d1-%s' %i, contents='x')
      self.CreateTempFile(tmpdir=tmpdir2, file_name='d2-%s' %i, contents='y')

    # We open a new temp file each time we reach rsync_buffer_lines of
    # listing output. On Windows, this will result in a 'too many open file
    # handles' error, so choose a larger value so as not to open so many files.
    rsync_buffer_config = [('GSUtil', 'rsync_buffer_lines',
                            '50' if IS_WINDOWS else '2')]
    # Run gsutil with config option to make buffer size << # files.
    with SetBotoConfigForTest(rsync_buffer_config):
      self.RunGsUtil(['rsync', '-d', tmpdir1, tmpdir2])
    listing1 = _TailSet(tmpdir1, self._FlatListDir(tmpdir1))
    listing2 = _TailSet(tmpdir2, self._FlatListDir(tmpdir2))
    self.assertEquals(listing1, listing2)

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', tmpdir1, tmpdir2], return_stderr=True))
    _Check()

  @unittest.skipUnless(UsingCrcmodExtension(crcmod),
                       'Test requires fast crcmod.')
  def test_bucket_to_dir_minus_d(self):
    """Tests that flat and recursive rsync bucket to dir works correctly."""
    # Create bucket and dir with 1 overlapping object, 1 extra object at root
    # level in each, and 1 extra object 1 level down in each, where one of the
    # objects starts with "." to test that we don't skip those objects. Make the
    # overlapping objects named the same but with different content, to test
    # that we detect and properly copy in that case.
    bucket_uri = self.CreateBucket()
    tmpdir = self.CreateTempDir()
    subdir = os.path.join(tmpdir, 'subdir')
    os.mkdir(subdir)
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket_uri, object_name='.obj2',
                      contents='.obj2')
    self.CreateObject(bucket_uri=bucket_uri, object_name='subdir/obj3',
                      contents='subdir/obj3')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.OBJ2')
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj4', contents='obj4')
    self.CreateTempFile(tmpdir=subdir, file_name='obj5', contents='subdir/obj5')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-d', suri(bucket_uri), tmpdir])
      listing1 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      listing2 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      # Bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Dir should have content like bucket but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were not synchronized (bucket to dir sync doesn't use checksums
      # unless you specify -c).
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket_uri, '.obj2')], return_stdout=True))
      with open(os.path.join(tmpdir, '.obj2')) as f:
        self.assertEquals('.OBJ2', '\n'.join(f.readlines()))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket_uri), tmpdir], return_stderr=True))
    _Check2()

    # Now rerun the sync with the -c option.
    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      """Tests rsync -c works as expected."""
      self.RunGsUtil(['rsync', '-d', '-c', suri(bucket_uri), tmpdir])
      listing1 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      listing2 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      # Bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Dir should have content like bucket but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
      # Assert that the src/dest objects that had same length but different
      # content were synchronized (bucket to dir sync with -c uses checksums).
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket_uri, '.obj2')], return_stdout=True))
      with open(os.path.join(tmpdir, '.obj2')) as f:
        self.assertEquals('.obj2', '\n'.join(f.readlines()))
    _Check3()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check4():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-c', suri(bucket_uri), tmpdir], return_stderr=True))
    _Check4()

    # Now add and remove some objects in dir and bucket and test rsync -r.
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj6',
                      contents='obj6')
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj7', contents='obj7')
    self.RunGsUtil(['rm', suri(bucket_uri, 'obj1')])
    os.unlink(os.path.join(tmpdir, '.obj2'))

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check5():
      self.RunGsUtil(['rsync', '-d', '-r', suri(bucket_uri), tmpdir])
      listing1 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      listing2 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      # Bucket should have un-altered content.
      self.assertEquals(listing1, set(['/.obj2', '/obj6', '/subdir/obj3']))
      # Dir should have content like bucket but without the subdir objects
      # synchronized.
      self.assertEquals(listing2, set(['/.obj2', '/obj6', '/subdir/obj3']))
    _Check5()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check6():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-r', suri(bucket_uri), tmpdir], return_stderr=True))
    _Check6()

  def test_bucket_to_dir_minus_d_with_fname_case_change(self):
    """Tests that name case changes work correctly.

    Example:

    Windows filenames are case-preserving in what you wrote, but case-
    insensitive when compared. If you synchronize from FS to cloud and then
    change case-naming in local files, you could end up with this situation:

    Cloud copy is called .../TiVo/...
    FS copy is called      .../Tivo/...

    Then, if you sync from cloud to FS, if rsync doesn't recognize that on
    Windows these names are identical, each rsync run will cause both a copy
    and a delete to be executed.
    """
    # Create bucket and dir with same objects, but dir copy has different name
    # case.
    bucket_uri = self.CreateBucket()
    tmpdir = self.CreateTempDir()
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj1',
                      contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='Obj1', contents='obj1')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      output = self.RunGsUtil(
          ['rsync', '-d', '-r', suri(bucket_uri), tmpdir], return_stderr=True)
      # Nothing should be copied or removed under Windows.
      if IS_WINDOWS:
        self.assertEquals(NO_CHANGES, output)
      else:
        self.assertNotEquals(NO_CHANGES, output)
    _Check1()

  def test_bucket_to_dir_minus_d_with_leftover_dir_placeholder(self):
    """Tests that we correctly handle leftover dir placeholders.

    See comments in gslib.commands.rsync._FieldedListingIterator for details.
    """
    bucket_uri = self.CreateBucket()
    tmpdir = self.CreateTempDir()
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj1',
                      contents='obj1')
    # Create a placeholder like what can be left over by web GUI tools.
    key_uri = bucket_uri.clone_replace_name('/')
    key_uri.set_contents_from_string('')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      output = self.RunGsUtil(
          ['rsync', '-d', '-r', suri(bucket_uri), tmpdir], return_stderr=True)
      listing1 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      listing2 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      # Bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '//']))
      # Bucket should not have the placeholder object.
      self.assertEquals(listing2, set(['/obj1']))
    _Check1()

  @unittest.skipIf(IS_WINDOWS, 'os.symlink() is not available on Windows.')
  def test_rsync_minus_d_minus_e(self):
    """Tests that rsync -e ignores symlinks."""
    tmpdir = self.CreateTempDir()
    subdir = os.path.join(tmpdir, 'subdir')
    os.mkdir(subdir)
    bucket_uri = self.CreateBucket()
    fpath1 = self.CreateTempFile(
        tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    self.CreateTempFile(tmpdir=subdir, file_name='obj3', contents='subdir/obj3')
    good_symlink_path = os.path.join(tmpdir, 'symlink1')
    os.symlink(fpath1, good_symlink_path)
    # Make a symlink that points to a non-existent path to test that -e also
    # handles that case.
    bad_symlink_path = os.path.join(tmpdir, 'symlink2')
    os.symlink(os.path.join('/', 'non-existent'), bad_symlink_path)
    self.CreateObject(bucket_uri=bucket_uri, object_name='.obj2',
                      contents='.OBJ2')
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj4',
                      contents='obj4')
    self.CreateObject(bucket_uri=bucket_uri, object_name='subdir/obj5',
                      contents='subdir/obj5')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Ensure listings match the commented expectations."""
      self.RunGsUtil(['rsync', '-d', '-e', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(
          listing1,
          set(['/obj1', '/.obj2', '/subdir/obj3', '/symlink1', '/symlink2']))
      # Bucket should have content like dir but without the symlink, and
      # without subdir objects synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj5']))
    _Check1()

    # Now remove invalid symlink and run without -e, and see that symlink gets
    # copied (as file to which it points). Use @Retry as hedge against bucket
    # listing eventual consistency.
    os.unlink(bad_symlink_path)
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-d', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(
          listing1, set(['/obj1', '/.obj2', '/subdir/obj3', '/symlink1']))
      # Bucket should have content like dir but without the symlink, and
      # without subdir objects synchronized.
      self.assertEquals(
          listing2, set(['/obj1', '/.obj2', '/subdir/obj5', '/symlink1']))
      self.assertEquals('obj1', self.RunGsUtil(
          ['cat', suri(bucket_uri, 'symlink1')], return_stdout=True))
    _Check2()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check3():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', tmpdir, suri(bucket_uri)], return_stderr=True))
    _Check3()

  @SkipForS3('S3 does not support composite objects')
  def test_bucket_to_bucket_minus_d_with_composites(self):
    """Tests that rsync works with composite objects (which don't have MD5s)."""
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='.obj2',
                      contents='.obj2')
    self.RunGsUtil(
        ['compose', suri(bucket1_uri, 'obj1'), suri(bucket1_uri, '.obj2'),
         suri(bucket1_uri, 'obj3')])
    self.CreateObject(bucket_uri=bucket2_uri, object_name='.obj2',
                      contents='.OBJ2')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj4',
                      contents='obj4')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      self.RunGsUtil(['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/obj3']))
      # Second bucket should have content like first bucket but without the
      # subdir objects synchronized.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/obj3']))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

  def test_bucket_to_bucket_minus_d_empty_dest(self):
    """Tests working with empty dest bucket (iter runs out before src iter)."""
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='.obj2',
                      contents='.obj2')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      self.RunGsUtil(['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      self.assertEquals(listing1, set(['/obj1', '/.obj2']))
      self.assertEquals(listing2, set(['/obj1', '/.obj2']))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

  def test_bucket_to_bucket_minus_d_empty_src(self):
    """Tests working with empty src bucket (iter runs out before dst iter)."""
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket2_uri, object_name='obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='.obj2',
                      contents='.obj2')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      self.RunGsUtil(['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)])
      stderr = self.RunGsUtil(['ls', suri(bucket1_uri, '**')],
                              expected_status=1, return_stderr=True)
      self.assertIn('One or more URLs matched no objects', stderr)
      stderr = self.RunGsUtil(['ls', suri(bucket2_uri, '**')],
                              expected_status=1, return_stderr=True)
      self.assertIn('One or more URLs matched no objects', stderr)
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

  def test_rsync_minus_d_minus_p(self):
    """Tests that rsync -p preserves ACLs."""
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket1_uri, object_name='obj1',
                      contents='obj1')
    # Set public-read (non-default) ACL so we can verify that rsync -p works.
    self.RunGsUtil(['acl', 'set', 'public-read', suri(bucket1_uri, 'obj1')])

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync -p works as expected."""
      self.RunGsUtil(['rsync', '-d', '-p', suri(bucket1_uri),
                      suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      self.assertEquals(listing1, set(['/obj1']))
      self.assertEquals(listing2, set(['/obj1']))
      acl1_json = self.RunGsUtil(['acl', 'get', suri(bucket1_uri, 'obj1')],
                                 return_stdout=True)
      acl2_json = self.RunGsUtil(['acl', 'get', suri(bucket2_uri, 'obj1')],
                                 return_stdout=True)
      self.assertEquals(acl1_json, acl2_json)
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-p', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

  def test_rsync_to_nonexistent_bucket_subdir(self):
    """Tests that rsync to non-existent bucket subdir works."""
    # Create dir with some objects and empty bucket.
    tmpdir = self.CreateTempDir()
    subdir = os.path.join(tmpdir, 'subdir')
    os.mkdir(subdir)
    bucket_url = self.CreateBucket()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    self.CreateTempFile(tmpdir=subdir, file_name='obj3', contents='subdir/obj3')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-r', tmpdir, suri(bucket_url, 'subdir')])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(
          suri(bucket_url, 'subdir'),
          self._FlatListBucket(bucket_url.clone_replace_name('subdir')))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/subdir/obj3']))
      # Bucket subdir should have content like dir.
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/subdir/obj3']))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-r', tmpdir, suri(bucket_url, 'subdir')],
          return_stderr=True))
    _Check2()

  def test_rsync_from_nonexistent_bucket(self):
    """Tests that rsync from a non-existent bucket subdir fails gracefully."""
    tmpdir = self.CreateTempDir()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    bucket_url_str = '%s://%s' % (
        self.default_provider, self.nonexistent_bucket_name)
    stderr = self.RunGsUtil(['rsync', '-d', bucket_url_str, tmpdir],
                            expected_status=1, return_stderr=True)
    self.assertIn('Caught non-retryable exception', stderr)
    listing = _TailSet(tmpdir, self._FlatListDir(tmpdir))
    # Dir should have un-altered content.
    self.assertEquals(listing, set(['/obj1', '/.obj2']))

  def test_rsync_to_nonexistent_bucket(self):
    """Tests that rsync from a non-existent bucket subdir fails gracefully."""
    tmpdir = self.CreateTempDir()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    bucket_url_str = '%s://%s' % (
        self.default_provider, self.nonexistent_bucket_name)
    stderr = self.RunGsUtil(['rsync', '-d', bucket_url_str, tmpdir],
                            expected_status=1, return_stderr=True)
    self.assertIn('Caught non-retryable exception', stderr)
    listing = _TailSet(tmpdir, self._FlatListDir(tmpdir))
    # Dir should have un-altered content.
    self.assertEquals(listing, set(['/obj1', '/.obj2']))

  def test_bucket_to_bucket_minus_d_with_overwrite_and_punc_chars(self):
    """Tests that punc chars in filenames don't confuse sort order."""
    bucket1_uri = self.CreateBucket()
    bucket2_uri = self.CreateBucket()
    # Create 2 objects in each bucket, with one overwritten with a name that's
    # less than the next name in destination bucket when encoded, but not when
    # compared without encoding.
    self.CreateObject(bucket_uri=bucket1_uri, object_name='e/obj1',
                      contents='obj1')
    self.CreateObject(bucket_uri=bucket1_uri, object_name='e-1/.obj2',
                      contents='.obj2')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='e/obj1',
                      contents='OBJ1')
    self.CreateObject(bucket_uri=bucket2_uri, object_name='e-1/.obj2',
                      contents='.obj2')
    # Need to make sure the bucket listings are caught-up, otherwise the
    # rsync may not see all objects and fail to synchronize correctly.
    self.AssertNObjectsInBucket(bucket1_uri, 2)
    self.AssertNObjectsInBucket(bucket2_uri, 2)

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-rd', suri(bucket1_uri), suri(bucket2_uri)])
      listing1 = _TailSet(suri(bucket1_uri), self._FlatListBucket(bucket1_uri))
      listing2 = _TailSet(suri(bucket2_uri), self._FlatListBucket(bucket2_uri))
      # First bucket should have un-altered content.
      self.assertEquals(listing1, set(['/e/obj1', '/e-1/.obj2']))
      self.assertEquals(listing2, set(['/e/obj1', '/e-1/.obj2']))
      # Assert correct contents.
      self.assertEquals('obj1', self.RunGsUtil(
          ['cat', suri(bucket2_uri, 'e/obj1')], return_stdout=True))
      self.assertEquals('.obj2', self.RunGsUtil(
          ['cat', suri(bucket2_uri, 'e-1/.obj2')], return_stdout=True))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', suri(bucket1_uri), suri(bucket2_uri)],
          return_stderr=True))
    _Check2()

  def test_dir_to_bucket_minus_x(self):
    """Tests that rsync -x option works correctly."""
    # Create dir and bucket with 1 overlapping and 2 extra objects in each.
    tmpdir = self.CreateTempDir()
    bucket_uri = self.CreateBucket()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    self.CreateTempFile(tmpdir=tmpdir, file_name='.obj2', contents='.obj2')
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj3', contents='obj3')
    self.CreateObject(bucket_uri=bucket_uri, object_name='.obj2',
                      contents='.obj2')
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj4',
                      contents='obj4')
    self.CreateObject(bucket_uri=bucket_uri, object_name='obj5',
                      contents='obj5')

    # Need to make sure the bucket listing is caught-up, otherwise the
    # first rsync may not see .obj2 and overwrite it.
    self.AssertNObjectsInBucket(bucket_uri, 3)

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      """Tests rsync works as expected."""
      self.RunGsUtil(['rsync', '-d', '-x', 'obj[34]', tmpdir, suri(bucket_uri)])
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/.obj2', '/obj3']))
      # Bucket should have content like dir but ignoring obj3 from dir and not
      # deleting obj4 from bucket (per exclude regex).
      self.assertEquals(listing2, set(['/obj1', '/.obj2', '/obj4']))
    _Check1()

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check2():
      # Check that re-running the same rsync command causes no more changes.
      self.assertEquals(NO_CHANGES, self.RunGsUtil(
          ['rsync', '-d', '-x', 'obj[34]', tmpdir, suri(bucket_uri)],
          return_stderr=True))
    _Check2()

  @unittest.skipIf(IS_WINDOWS,
                   "os.chmod() won't make file unreadable on Windows.")
  def test_dir_to_bucket_minus_C(self):
    """Tests that rsync -C option works correctly."""
    # Create dir with 3 objects, the middle of which is unreadable.
    tmpdir = self.CreateTempDir()
    bucket_uri = self.CreateBucket()
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj1', contents='obj1')
    path = self.CreateTempFile(tmpdir=tmpdir, file_name='obj2', contents='obj2')
    os.chmod(path, 0)
    self.CreateTempFile(tmpdir=tmpdir, file_name='obj3', contents='obj3')

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check():
      """Tests rsync works as expected."""
      stderr =  self.RunGsUtil(['rsync', '-C', tmpdir, suri(bucket_uri)],
                               expected_status=1, return_stderr=True)
      self.assertIn('1 files/objects could not be copied/removed.', stderr)
      listing1 = _TailSet(tmpdir, self._FlatListDir(tmpdir))
      listing2 = _TailSet(suri(bucket_uri), self._FlatListBucket(bucket_uri))
      # Dir should have un-altered content.
      self.assertEquals(listing1, set(['/obj1', '/obj2', '/obj3']))
      # Bucket should have obj1 and obj3 even though obj2 was unreadable.
      self.assertEquals(listing2, set(['/obj1', '/obj3']))
    _Check()
