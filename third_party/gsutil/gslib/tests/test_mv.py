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
"""Integration tests for mv command."""

from __future__ import absolute_import

import os

import gslib.tests.testcase as testcase
from gslib.tests.util import ObjectToURI as suri
from gslib.tests.util import SequentialAndParallelTransfer
from gslib.util import Retry


class TestMv(testcase.GsUtilIntegrationTestCase):
  """Integration tests for mv command."""

  def test_moving(self):
    """Tests moving two buckets, one with 2 objects and one with 0 objects."""
    bucket1_uri = self.CreateBucket(test_objects=2)
    self.AssertNObjectsInBucket(bucket1_uri, 2)
    bucket2_uri = self.CreateBucket()
    self.AssertNObjectsInBucket(bucket2_uri, 0)

    # Move two objects from bucket1 to bucket2.
    objs = [bucket1_uri.clone_replace_key(key).versionless_uri
            for key in bucket1_uri.list_bucket()]
    cmd = (['-m', 'mv'] + objs + [suri(bucket2_uri)])
    stderr = self.RunGsUtil(cmd, return_stderr=True)
    # Rewrite API may output an additional 'Copying' progress notification.
    self.assertGreaterEqual(stderr.count('Copying'), 2)
    self.assertLessEqual(stderr.count('Copying'), 4)
    self.assertEqual(stderr.count('Copying') % 2, 0)
    self.assertEqual(stderr.count('Removing'), 2)

    self.AssertNObjectsInBucket(bucket1_uri, 0)
    self.AssertNObjectsInBucket(bucket2_uri, 2)

    # Remove one of the objects.
    objs = [bucket2_uri.clone_replace_key(key).versionless_uri
            for key in bucket2_uri.list_bucket()]
    obj1 = objs[0]
    self.RunGsUtil(['rm', obj1])

    self.AssertNObjectsInBucket(bucket1_uri, 0)
    self.AssertNObjectsInBucket(bucket2_uri, 1)

    # Move the 1 remaining object back.
    objs = [suri(bucket2_uri.clone_replace_key(key))
            for key in bucket2_uri.list_bucket()]
    cmd = (['-m', 'mv'] + objs + [suri(bucket1_uri)])
    stderr = self.RunGsUtil(cmd, return_stderr=True)
    # Rewrite API may output an additional 'Copying' progress notification.
    self.assertGreaterEqual(stderr.count('Copying'), 1)
    self.assertLessEqual(stderr.count('Copying'), 2)
    self.assertEqual(stderr.count('Removing'), 1)

    self.AssertNObjectsInBucket(bucket1_uri, 1)
    self.AssertNObjectsInBucket(bucket2_uri, 0)

  def test_move_dir_to_bucket(self):
    """Tests moving a local directory to a bucket."""
    bucket_uri = self.CreateBucket()
    dir_to_move = self.CreateTempDir(test_files=2)
    self.RunGsUtil(['mv', dir_to_move, suri(bucket_uri)])
    self.AssertNObjectsInBucket(bucket_uri, 2)

  @SequentialAndParallelTransfer
  def test_stdin_args(self):
    """Tests mv with the -I option."""
    tmpdir = self.CreateTempDir()
    fpath1 = self.CreateTempFile(tmpdir=tmpdir, contents='data1')
    fpath2 = self.CreateTempFile(tmpdir=tmpdir, contents='data2')
    bucket_uri = self.CreateBucket()
    self.RunGsUtil(['mv', '-I', suri(bucket_uri)],
                   stdin='\n'.join((fpath1, fpath2)))

    # Use @Retry as hedge against bucket listing eventual consistency.
    @Retry(AssertionError, tries=3, timeout_secs=1)
    def _Check1():
      stdout = self.RunGsUtil(['ls', suri(bucket_uri)], return_stdout=True)
      self.assertIn(os.path.basename(fpath1), stdout)
      self.assertIn(os.path.basename(fpath2), stdout)
      self.assertNumLines(stdout, 2)
    _Check1()

  def test_mv_no_clobber(self):
    """Tests mv with the -n option."""
    fpath1 = self.CreateTempFile(contents='data1')
    bucket_uri = self.CreateBucket()
    object_uri = self.CreateObject(bucket_uri=bucket_uri, contents='data2')
    stderr = self.RunGsUtil(['mv', '-n', fpath1, suri(object_uri)],
                            return_stderr=True)
    # Copy should be skipped and source file should not be removed.
    self.assertIn('Skipping existing item: %s' % suri(object_uri), stderr)
    self.assertNotIn('Removing %s' % suri(fpath1), stderr)
    # Object content should be unchanged.
    contents = self.RunGsUtil(['cat', suri(object_uri)], return_stdout=True)
    self.assertEqual(contents, 'data2')

