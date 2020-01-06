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
"""Tests for signurl command."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from datetime import datetime
from datetime import timedelta
import pkgutil

import gslib.commands.signurl
from gslib.commands.signurl import HAVE_OPENSSL
from gslib.exception import CommandException
import gslib.tests.testcase as testcase
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.util import ObjectToURI as suri
from gslib.tests.util import SetBotoConfigForTest
from gslib.tests.util import unittest
import gslib.tests.signurl_signatures as sigs


# pylint: disable=protected-access
@unittest.skipUnless(HAVE_OPENSSL, 'signurl requires pyopenssl.')
@SkipForS3('Signed URLs are only supported for gs:// URLs.')
class TestSignUrl(testcase.GsUtilIntegrationTestCase):
  """Integration tests for signurl command."""

  def _GetJSONKsFile(self):
    if not hasattr(self, 'json_ks_file'):
      # Dummy json keystore constructed from test.p12.
      contents = pkgutil.get_data('gslib', 'tests/test_data/test.json')
      self.json_ks_file = self.CreateTempFile(contents=contents)
    return self.json_ks_file

  def _GetKsFile(self):
    if not hasattr(self, 'ks_file'):
      # Dummy pkcs12 keystore generated with the command

      # openssl req -new -passout pass:notasecret -batch \
      # -x509 -keyout signed_url_test.key -out signed_url_test.pem \
      # -subj '/CN=test.apps.googleusercontent.com'

      # &&

      # openssl pkcs12 -export -passin pass:notasecret \
      # -passout pass:notasecret -inkey signed_url_test.key \
      # -in signed_url_test.pem -out test.p12

      # &&

      # rm signed_url_test.key signed_url_test.pem
      contents = pkgutil.get_data('gslib', 'tests/test_data/test.p12')
      self.ks_file = self.CreateTempFile(contents=contents)
    return self.ks_file

  def testSignUrlInvalidDuration(self):
    """Tests signurl fails with out of bounds value for valid duration."""
    stderr = self.RunGsUtil(['signurl', '-d', '123d', 'ks_file', 'gs://uri'],
                            return_stderr=True,
                            expected_status=1)
    self.assertIn('CommandException: Max valid duration allowed is 7 days',
                  stderr)

  def testSignUrlOutputP12(self):
    """Tests signurl output of a sample object with pkcs12 keystore."""
    self._DoTestSignUrlOutput(self._GetKsFile())

  def testSignUrlOutputJSON(self):
    """Tests signurl output of a sample object with json keystore."""
    self._DoTestSignUrlOutput(self._GetJSONKsFile(), json_keystore=True)

  def _DoTestSignUrlOutput(self, ks_file, json_keystore=False):
    """Tests signurl output of a sample object."""

    bucket_uri = self.CreateBucket()
    object_uri = self.CreateObject(bucket_uri=bucket_uri, contents=b'z')
    cmd_base = ['signurl'] if json_keystore else ['signurl', '-p', 'notasecret']
    stdout = self.RunGsUtil(
        cmd_base +
        ['-m', 'PUT', ks_file, suri(object_uri)], return_stdout=True)

    self.assertIn('x-goog-credential=test%40developer.gserviceaccount.com',
                  stdout)
    self.assertIn('x-goog-expires=3600', stdout)
    self.assertIn('%2Fus-central1%2F', stdout)
    self.assertIn('\tPUT\t', stdout)

  def testSignUrlWithURLEncodeRequiredChars(self):
    objs = [
        'gs://example.org/test 1', 'gs://example.org/test/test 2',
        'gs://example.org/Аудиоарi хив'
    ]
    expected_partial_urls = [
        'https://storage.googleapis.com/example.org/test%201?x-goog-signature=',
        ('https://storage.googleapis.com/example.org/test/test%202'
         '?x-goog-signature='),
        ('https://storage.googleapis.com/example.org/%D0%90%D1%83%D0%B4%D0%B8%D'
         '0%BE%D0%B0%D1%80i%20%D1%85%D0%B8%D0%B2?x-goog-signature=')
    ]

    self.assertEquals(len(objs), len(expected_partial_urls))

    cmd_args = [
        'signurl', '-m', 'PUT', '-p', 'notasecret', '-r', 'us',
        self._GetKsFile()
    ]
    cmd_args.extend(objs)

    stdout = self.RunGsUtil(cmd_args, return_stdout=True)

    lines = stdout.split('\n')
    # Header, signed urls, trailing newline.
    self.assertEquals(len(lines), len(objs) + 2)

    # Strip the header line to make the indices line up.
    lines = lines[1:]

    for obj, line, partial_url in zip(objs, lines, expected_partial_urls):
      self.assertIn(obj, line)
      self.assertIn(partial_url, line)
      self.assertIn('x-goog-credential=test%40developer.gserviceaccount.com',
                    line)
    self.assertIn('%2Fus%2F', stdout)

  def testSignUrlWithWildcard(self):
    objs = ['test1', 'test2', 'test3']
    obj_urls = []
    bucket = self.CreateBucket()

    for obj_name in objs:
      obj_urls.append(
          self.CreateObject(bucket_uri=bucket,
                            object_name=obj_name,
                            contents=b''))

    stdout = self.RunGsUtil(
        ['signurl', '-p', 'notasecret',
         self._GetKsFile(),
         suri(bucket) + '/*'],
        return_stdout=True)

    # Header, 3 signed urls, trailing newline
    self.assertEquals(len(stdout.split('\n')), 5)

    for obj_url in obj_urls:
      self.assertIn(suri(obj_url), stdout)

  def testSignUrlOfNonObjectUrl(self):
    """Tests the signurl output of a non-existent file."""
    self.RunGsUtil(['signurl', self._GetKsFile(), 'gs://'],
                   expected_status=1,
                   stdin='notasecret')
    self.RunGsUtil(['signurl', 'file://tmp/abc'], expected_status=1)


@unittest.skipUnless(HAVE_OPENSSL, 'signurl requires pyopenssl.')
class UnitTestSignUrl(testcase.GsUtilUnitTestCase):
  """Unit tests for the signurl command."""

  # Helpful for comparing mismatched signed URLs that would be truncated.
  # https://stackoverflow.com/questions/14493670/how-to-set-self-maxdiff-in-nose-to-get-full-diff-output
  maxDiff = None

  def setUp(self):
    super(UnitTestSignUrl, self).setUp()
    ks_contents = pkgutil.get_data('gslib', 'tests/test_data/test.p12')
    self.key, self.client_email = gslib.commands.signurl._ReadKeystore(
        ks_contents, 'notasecret')

    def fake_now():
      return datetime(1900, 1, 1, 0, 5, 55)

    gslib.commands.signurl._NowUTC = fake_now

  def testDurationSpec(self):
    tests = [
        ('1h', timedelta(hours=1)),
        ('2d', timedelta(days=2)),
        ('5D', timedelta(days=5)),
        ('35s', timedelta(seconds=35)),
        ('1h', timedelta(hours=1)),
        ('33', timedelta(hours=33)),
        ('22m', timedelta(minutes=22)),
        ('3.7', None),
        ('27Z', None),
    ]

    for inp, expected in tests:
      try:
        td = gslib.commands.signurl._DurationToTimeDelta(inp)
        self.assertEquals(td, expected)
      except CommandException:
        if expected is not None:
          self.fail('{0} failed to parse')

  def testSignPut(self):
    """Tests the _GenSignedUrl function with a PUT method."""
    expected = sigs.TEST_SIGN_PUT_SIG

    duration = timedelta(seconds=3600)
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          self.key,
          client_id=self.client_email,
          method='RESUMABLE',
          gcs_path='test/test.txt',
          duration=duration,
          logger=self.logger,
          region='us-east',
          content_type='')
    self.assertEquals(expected, signed_url)

  def testSignResumable(self):
    """Tests the _GenSignedUrl function with a RESUMABLE method."""
    expected = sigs.TEST_SIGN_RESUMABLE

    class MockLogger(object):

      def __init__(self):
        self.warning_issued = False

      def warn(self, unused_msg):
        self.warning_issued = True

    mock_logger = MockLogger()
    duration = timedelta(seconds=3600)
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          self.key,
          client_id=self.client_email,
          method='RESUMABLE',
          gcs_path='test/test.txt',
          duration=duration,
          logger=mock_logger,
          region='us-east',
          content_type='')
    self.assertEquals(expected, signed_url)
    # Resumable uploads with no content-type should issue a warning.
    self.assertTrue(mock_logger.warning_issued)

    mock_logger2 = MockLogger()
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          self.key,
          client_id=self.client_email,
          method='RESUMABLE',
          gcs_path='test/test.txt',
          duration=duration,
          logger=mock_logger2,
          region='us-east',
          content_type='image/jpeg')
    # No warning, since content type was included.
    self.assertFalse(mock_logger2.warning_issued)

  def testSignurlPutContentype(self):
    """Tests the _GenSignedUrl function a PUT method and content type."""
    expected = sigs.TEST_SIGN_URL_PUT_CONTENT

    duration = timedelta(seconds=3600)
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          self.key,
          client_id=self.client_email,
          method='PUT',
          gcs_path='test/test.txt',
          duration=duration,
          logger=self.logger,
          region='eu',
          content_type='text/plain')
    self.assertEquals(expected, signed_url)

  def testSignurlGet(self):
    """Tests the _GenSignedUrl function with a GET method."""
    expected = sigs.TEST_SIGN_URL_GET

    duration = timedelta(seconds=0)
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          self.key,
          client_id=self.client_email,
          method='GET',
          gcs_path='test/test.txt',
          duration=duration,
          logger=self.logger,
          region='asia',
          content_type='')
    self.assertEquals(expected, signed_url)

  def testSignurlGetWithJSONKey(self):
    """Tests _GenSignedUrl with a GET method and the test JSON private key."""
    expected = sigs.TEST_SIGN_URL_GET_WITH_JSON_KEY

    json_contents = pkgutil.get_data('gslib',
                                     'tests/test_data/test.json').decode()
    key, client_email = gslib.commands.signurl._ReadJSONKeystore(json_contents)

    duration = timedelta(seconds=0)
    with SetBotoConfigForTest([('Credentials', 'gs_host',
                                'storage.googleapis.com')]):
      signed_url = gslib.commands.signurl._GenSignedUrl(
          key,
          client_id=client_email,
          method='GET',
          gcs_path='test/test.txt',
          duration=duration,
          logger=self.logger,
          region='asia',
          content_type='')
    self.assertEquals(expected, signed_url)
