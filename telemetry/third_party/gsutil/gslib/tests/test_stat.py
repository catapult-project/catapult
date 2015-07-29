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
"""Tests for stat command."""

from __future__ import absolute_import

from gslib.cs_api_map import ApiSelector
import gslib.tests.testcase as testcase
from gslib.tests.util import ObjectToURI as suri


class TestStat(testcase.GsUtilIntegrationTestCase):
  """Integration tests for stat command."""

  def test_stat_output(self):
    """Tests stat output of a single object."""
    object_uri = self.CreateObject(contents='z')
    stdout = self.RunGsUtil(['stat', suri(object_uri)], return_stdout=True)
    self.assertIn(object_uri.uri, stdout)
    self.assertIn('Creation time:', stdout)

    # Cache-Control and Content-Encoding can be different depending on
    # whether the JSON or XML API is used.  For JSON, only max-age and
    # no-cache are respected.  Although the object field will be populated
    # with whatever we set, the actual header returned from the JSON API
    # may differ from it (and differ from the XML response for the same object).
    #
    # Likewise, with contentEncoding, the field value and the header value
    # are not guaranteed to match or be the same across APIs.
    #
    # JSON will not return a Cache-control or content-encoding with the
    # current test object creation, so check these only for the XML API.
    if self.default_provider == 'gs':
      if self.test_api == ApiSelector.XML:
        self.assertIn('Cache-Control:', stdout)
        self.assertIn('Content-Encoding:', stdout)
      self.assertIn('Generation:', stdout)
      self.assertIn('Metageneration:', stdout)
      self.assertIn('Hash (crc32c):', stdout)
      self.assertIn('Hash (md5):', stdout)
    self.assertIn('Content-Length:', stdout)
    self.assertIn('Content-Type:', stdout)
    self.assertIn('ETag:', stdout)

  def test_minus_q_stat(self):
    object_uri = self.CreateObject(contents='z')
    stdout = self.RunGsUtil(['-q', 'stat', suri(object_uri)],
                            return_stdout=True)
    self.assertEquals(0, len(stdout))
    stdout = self.RunGsUtil(['-q', 'stat', suri(object_uri, 'junk')],
                            return_stdout=True, expected_status=1)
    self.assertEquals(0, len(stdout))

  def test_stat_of_non_object_uri(self):
    self.RunGsUtil(['-q', 'stat', 'gs://'], expected_status=1)
    self.RunGsUtil(['-q', 'stat', 'gs://bucket/object'], expected_status=1)
    self.RunGsUtil(['-q', 'stat', 'file://tmp/abc'], expected_status=1)

  def test_stat_one_missing(self):
    bucket_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket_uri, object_name='notmissing',
                      contents='z')
    stdout, stderr = self.RunGsUtil(
        ['stat', suri(bucket_uri, 'missing'), suri(bucket_uri, 'notmissing')],
        expected_status=1, return_stdout=True, return_stderr=True)
    self.assertIn('No URLs matched %s' % suri(bucket_uri, 'missing'), stderr)
    self.assertIn('%s:' % suri(bucket_uri, 'notmissing'), stdout)

  def test_stat_one_missing_wildcard(self):
    bucket_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket_uri, object_name='notmissing',
                      contents='z')
    stdout, stderr = self.RunGsUtil(
        ['stat', suri(bucket_uri, 'missin*'), suri(bucket_uri, 'notmissin*')],
        expected_status=1, return_stdout=True, return_stderr=True)
    self.assertIn('No URLs matched %s' % suri(bucket_uri, 'missin*'), stderr)
    self.assertIn('%s:' % suri(bucket_uri, 'notmissing'), stdout)

  def test_stat_bucket_wildcard(self):
    bucket_uri = self.CreateBucket()
    self.CreateObject(bucket_uri=bucket_uri, object_name='foo', contents='z')
    stat_string = suri(bucket_uri)[:-1] + '?/foo'
    self.RunGsUtil(['stat', stat_string])
    stat_string2 = suri(bucket_uri)[:-1] + '*/foo'
    self.RunGsUtil(['stat', stat_string2])

  def test_stat_object_wildcard(self):
    bucket_uri = self.CreateBucket()
    object1_uri = self.CreateObject(bucket_uri=bucket_uri, object_name='foo1',
                                    contents='z')
    object2_uri = self.CreateObject(bucket_uri=bucket_uri, object_name='foo2',
                                    contents='z')
    stat_string = suri(object1_uri)[:-2] + '*'
    stdout = self.RunGsUtil(['stat', stat_string], return_stdout=True)
    self.assertIn(suri(object1_uri), stdout)
    self.assertIn(suri(object2_uri), stdout)

