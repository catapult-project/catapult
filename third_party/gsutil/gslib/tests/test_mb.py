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
"""Integration tests for mb command."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import boto
import gslib.tests.testcase as testcase
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.testcase.integration_testcase import SkipForXML
from gslib.tests.util import ObjectToURI as suri
from gslib.utils.retention_util import SECONDS_IN_DAY
from gslib.utils.retention_util import SECONDS_IN_MONTH
from gslib.utils.retention_util import SECONDS_IN_YEAR

BUCKET_LOCK_SKIP_MSG = ('gsutil does not support bucket lock operations for '
                        'S3 buckets.')


class TestMb(testcase.GsUtilIntegrationTestCase):
  """Integration tests for mb command."""

  @SkipForS3('S3 returns success when bucket already exists.')
  def test_mb_bucket_exists(self):
    bucket_uri = self.CreateBucket()
    stderr = self.RunGsUtil(['mb', suri(bucket_uri)],
                            expected_status=1,
                            return_stderr=True)
    self.assertIn('already exists', stderr)

  def test_non_ascii_project_fails(self):
    stderr = self.RunGsUtil(['mb', '-p', 'ã', 'gs://fobarbaz'],
                            expected_status=1,
                            return_stderr=True)
    self.assertIn('Invalid non-ASCII', stderr)

  @SkipForS3(BUCKET_LOCK_SKIP_MSG)
  def test_create_with_retention_seconds(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--retention', '60s', suri(bucket_uri)])
    self.VerifyRetentionPolicy(bucket_uri,
                               expected_retention_period_in_seconds=60)

  @SkipForS3(BUCKET_LOCK_SKIP_MSG)
  def test_create_with_retention_days(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--retention', '1d', suri(bucket_uri)])
    self.VerifyRetentionPolicy(
        bucket_uri, expected_retention_period_in_seconds=SECONDS_IN_DAY)

  @SkipForS3(BUCKET_LOCK_SKIP_MSG)
  def test_create_with_retention_months(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--retention', '1m', suri(bucket_uri)])
    self.VerifyRetentionPolicy(
        bucket_uri, expected_retention_period_in_seconds=SECONDS_IN_MONTH)

  @SkipForS3(BUCKET_LOCK_SKIP_MSG)
  def test_create_with_retention_years(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--retention', '1y', suri(bucket_uri)])
    self.VerifyRetentionPolicy(
        bucket_uri, expected_retention_period_in_seconds=SECONDS_IN_YEAR)

  @SkipForS3(BUCKET_LOCK_SKIP_MSG)
  def test_create_with_retention_invalid_arg(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    stderr = self.RunGsUtil(['mb', '--retention', '1second',
                             suri(bucket_uri)],
                            expected_status=1,
                            return_stderr=True)
    self.assertRegexpMatches(stderr, r'Incorrect retention period specified')

  def test_create_with_retention_on_s3_urls_fails(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('s3://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    stderr = self.RunGsUtil(
        ['mb', '--retention', '1y', suri(bucket_uri)],
        expected_status=1,
        return_stderr=True)
    self.assertRegexpMatches(
        stderr, r'Retention policy can only be specified for GCS buckets.')

  @SkipForXML('Public access prevention only runs on GCS JSON API')
  def test_create_with_pap_enforced(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--pap', 'enforced', suri(bucket_uri)])
    self.VerifyPublicAccessPreventionValue(bucket_uri, 'enforced')

  @SkipForXML('Public access prevention only runs on GCS JSON API')
  def test_create_with_pap_unspecified(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    self.RunGsUtil(['mb', '--pap', 'unspecified', suri(bucket_uri)])
    self.VerifyPublicAccessPreventionValue(bucket_uri, 'unspecified')

  @SkipForXML('Public access prevention only runs on GCS JSON API')
  def test_create_with_pap_invalid_arg(self):
    bucket_name = self.MakeTempName('bucket')
    bucket_uri = boto.storage_uri('gs://%s' % (bucket_name.lower()),
                                  suppress_consec_slashes=False)
    stderr = self.RunGsUtil(['mb', '--pap', 'invalid_arg',
                             suri(bucket_uri)],
                            expected_status=1,
                            return_stderr=True)
    self.assertRegexpMatches(stderr, r'invalid_arg is not a valid value')
