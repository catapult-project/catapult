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
from datetime import timedelta
import pkgutil

import gslib.commands.signurl
from gslib.commands.signurl import HAVE_OPENSSL
from gslib.exception import CommandException
import gslib.tests.testcase as testcase
from gslib.tests.testcase.integration_testcase import SkipForS3
from gslib.tests.util import ObjectToURI as suri
from gslib.tests.util import unittest


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

  def testSignUrlOutputP12(self):
    """Tests signurl output of a sample object with pkcs12 keystore."""
    self._DoTestSignUrlOutput(self._GetKsFile())

  def testSignUrlOutputJSON(self):
    """Tests signurl output of a sample object with json keystore."""
    self._DoTestSignUrlOutput(self._GetJSONKsFile(), json_keystore=True)

  def _DoTestSignUrlOutput(self, ks_file, json_keystore=False):
    """Tests signurl output of a sample object."""
    object_url = self.CreateObject(contents='z')
    cmd_base = ['signurl'] if json_keystore else ['signurl', '-p', 'notasecret']
    stdout = self.RunGsUtil(cmd_base + [ks_file, suri(object_url)],
                            return_stdout=True)

    self.assertIn(object_url.uri, stdout)
    self.assertIn('test@developer.gserviceaccount.com', stdout)
    self.assertIn('Expires=', stdout)
    self.assertIn('\tGET\t', stdout)

    stdout = self.RunGsUtil(cmd_base + ['-m', 'PUT', ks_file,
                                        'gs://test/test.txt'],
                            return_stdout=True)

    self.assertIn('test@developer.gserviceaccount.com', stdout)
    self.assertIn('Expires=', stdout)
    self.assertIn('\tPUT\t', stdout)

  def testSignUrlWithURLEncodeRequiredChars(self):
    objs = ['gs://example.org/test 1', 'gs://example.org/test/test 2',
            'gs://example.org/Аудиоарi хив']
    expected_partial_urls = [
        ('https://storage.googleapis.com/example.org/test%201?GoogleAccessId=te'
         'st@developer.gserviceaccount.com'),
        ('https://storage.googleapis.com/example.org/test/test%202?GoogleAccess'
         'Id=test@developer.gserviceaccount.com'),
        ('https://storage.googleapis.com/example.org/%D0%90%D1%83%D0%B4%D0%B8%D'
         '0%BE%D0%B0%D1%80i%20%D1%85%D0%B8%D0%B2?GoogleAccessId=test@developer.'
         'gserviceaccount.com')
        ]

    self.assertEquals(len(objs), len(expected_partial_urls))

    cmd_args = ['signurl', '-p', 'notasecret', self._GetKsFile()]
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

  def testSignUrlWithWildcard(self):
    objs = ['test1', 'test2', 'test3']
    bucket = self.CreateBucket()
    obj_urls = []

    for obj_name in objs:
      obj_urls.append(self.CreateObject(bucket_uri=bucket,
                                        object_name=obj_name, contents=''))

    stdout = self.RunGsUtil(['signurl', '-p',
                             'notasecret', self._GetKsFile(),
                             suri(bucket) + '/*'], return_stdout=True)

    # Header, 3 signed urls, trailing newline
    self.assertEquals(len(stdout.split('\n')), 5)

    for obj_url in obj_urls:
      self.assertIn(suri(obj_url), stdout)

  def testSignUrlOfNonObjectUrl(self):
    """Tests the signurl output of a non-existent file."""
    self.RunGsUtil(['signurl', self._GetKsFile(), 'gs://'],
                   expected_status=1, stdin='notasecret')
    self.RunGsUtil(['signurl', 'file://tmp/abc'], expected_status=1)


@unittest.skipUnless(HAVE_OPENSSL, 'signurl requires pyopenssl.')
class UnitTestSignUrl(testcase.GsUtilUnitTestCase):
  """Unit tests for the signurl command."""

  def setUp(self):
    super(UnitTestSignUrl, self).setUp()
    ks_contents = pkgutil.get_data('gslib', 'tests/test_data/test.p12')
    self.key, self.client_email = gslib.commands.signurl._ReadKeystore(
        ks_contents, 'notasecret')

  def testDurationSpec(self):
    tests = [('1h', timedelta(hours=1)),
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
    expected = ('https://storage.googleapis.com/test/test.txt?'
                'GoogleAccessId=test@developer.gserviceaccount.com'
                '&Expires=1391816302&Signature=A6QbgTA8cXZCtjy2xCr401bdi0e'
                '7zChTBQ6BX61L7AfytTGEQDMD%2BbvOQKjX7%2FsEh77cmzcSxOEKqTLUD'
                'bbkPgPqW3j8sGPSRX9VM58bgj1vt9yU8cRKoegFHXAqsATx2G5rc%2FvEl'
                'iFp9UWMfVj5TaukqlBAVuzZWlyx0aQa9tCKXRtC9YcxORxG41RfiowA2kd8'
                'XBTQt4M9XTzpVyr5rVMzfr2LvtGf9UAJvlt8p6T6nThl2vy9%2FwBoPcMFa'
                'OWQcGTagwjyKWDcI1vQPIFQLGftAcv3QnGZxZTtg8pZW%2FIxRJrBhfFfcA'
                'c62hDKyaU2YssSMy%2FjUJynWx3TIiJjhg%3D%3D')

    expiration = 1391816302
    signed_url = gslib.commands.signurl._GenSignedUrl(
        self.key, self.client_email, 'PUT', '', '', expiration,
        'test/test.txt', self.logger)
    self.assertEquals(expected, signed_url)

  def testSignResumable(self):
    """Tests the _GenSignedUrl function with a RESUMABLE method."""
    expected = ('https://storage.googleapis.com/test/test.txt?'
                'GoogleAccessId=test@developer.gserviceaccount.com'
                '&Expires=1391816302&Signature=UjGs%2FBkE910Twb3Pqt0%2Fq49yNm9'
                'xykmFYICOdgmdOxbiFtyjwrp%2FsjNgnu42UXuikzRVtM02nHyy8ZebWUome6'
                '6Vkk7CKQNndDL3sdJD7ErqVTU2DjOH0ZMhmFIxqAwLnShdMDnE%2FhV7iTeF8'
                'XjsM49IMxMvJiDuclzmxg4aJkkdrpodduxY8dtta1BKMWKjESzKn7nYxZcU06'
                'iRhWN76OyH7RtRA4SpO5SDdepzsD5TPzAKmPQKLBTlcHkRbx3FE7ZDFJ5hF1L'
                'ilSRr3GgD7E4kRFD3ybYuBQYEJJN5SIlpWw2n3De5QetxMGq6a%2FzkwA1zdc'
                'WHCbL%2FVAmHkfuDJg%3D%3D')

    class MockLogger(object):

      def __init__(self):
        self.warning_issued = False

      def warn(self, unused_msg):
        self.warning_issued = True

    mock_logger = MockLogger()
    expiration = 1391816302
    signed_url = gslib.commands.signurl._GenSignedUrl(
        self.key, self.client_email, 'RESUMABLE', '', '', expiration,
        'test/test.txt', mock_logger)
    self.assertEquals(expected, signed_url)
    # Resumable uploads with no content-type should issue a warning.
    self.assertTrue(mock_logger.warning_issued)

    mock_logger2 = MockLogger()
    signed_url = gslib.commands.signurl._GenSignedUrl(
        self.key, self.client_email, 'RESUMABLE', '', 'image/jpeg', expiration,
        'test/test.txt', mock_logger)
    # No warning, since content type was included.
    self.assertFalse(mock_logger2.warning_issued)

  def testSignurlPutContentype(self):
    """Tests the _GenSignedUrl function a PUT method and content type."""
    expected = ('https://storage.googleapis.com/test/test.txt?'
                'GoogleAccessId=test@developer.gserviceaccount.com&'
                'Expires=1391816302&Signature=APn%2BCCVcQrfc1fKQXrs'
                'PEZFj9%2FmASO%2BolR8xwgBY6PbWMkcCtrUVFBauP6t4NxqZO'
                'UnbOFYTZYzul0RC57ZkEWJp3VcyDIHcn6usEE%2FTzUHhbDCDW'
                'awAkZS7p8kO8IIACuJlF5s9xZmZzaEBtzF0%2BBOsGgBPBlg2y'
                'zrhFB6cyyAwNiUgmhLQaVkdobnSwtI5QJkvXoIjJb6hhLiVbLC'
                'rWdgSZVusjAKGlWCJsM%2B4TkCR%2Bi8AnrkECngcMHuJ9mYbS'
                'XI1VfEmcnRVcfkKkJGZGctaDIWK%2FMTEmfYCW6USt3Zk2WowJ'
                'SGuJHqEcFz0kyfAlkpmG%2Fl5E1FQROYqLN2kZQ%3D%3D')

    expiration = 1391816302
    signed_url = gslib.commands.signurl._GenSignedUrl(
        self.key, self.client_email, 'PUT', '', 'text/plain', expiration,
        'test/test.txt', self.logger)
    self.assertEquals(expected, signed_url)

  def testSignurlGet(self):
    """Tests the _GenSignedUrl function with a GET method."""
    expected = ('https://storage.googleapis.com/test/test.txt?'
                'GoogleAccessId=test@developer.gserviceaccount.com&'
                'Expires=0&Signature=TCZwe32cU%2BMksmLiSY9shHXQjLs1'
                'F3y%2F%2F1M0UhiK4qsPRVNZVwI7YWvv2qa2Xa%2BVBBafboF0'
                '1%2BWvx3ZG316pwpNIRR6y7jNnE0LvQmHE8afbm2VYCi%2B2JS'
                'ZK2YZFJAyEek8si53jhYQEmaRq1zPfGbX84B2FJ8v4iI%2FTC1'
                'I9OE5vHF0sWwIR9d73JDrFLjaync7QYFWRExdwvqlQX%2BPO3r'
                'OG9Ns%2BcQFIN7npnsVjH28yNY9gBzXya8LYmNvUx6bWHWZMiu'
                'fLwDZ0jejNeDZTOfQGRM%2B0vY7NslzaT06W1wo8P7McSkAZEl'
                'DCbhR0Vo1fturPMwmAhi88f0qzRzywbg%3D%3D')

    expiration = 0
    signed_url = gslib.commands.signurl._GenSignedUrl(
        self.key, self.client_email, 'GET', '', '', expiration, 'test/test.txt',
        self.logger)
    self.assertEquals(expected, signed_url)

  def testSignurlGetWithJSONKey(self):
    """Tests _GenSignedUrl with a GET method and the test JSON private key."""
    expected = ('https://storage.googleapis.com/test/test.txt?'
                'GoogleAccessId=test@developer.gserviceaccount.com&'
                'Expires=0&Signature=TCZwe32cU%2BMksmLiSY9shHXQjLs1'
                'F3y%2F%2F1M0UhiK4qsPRVNZVwI7YWvv2qa2Xa%2BVBBafboF0'
                '1%2BWvx3ZG316pwpNIRR6y7jNnE0LvQmHE8afbm2VYCi%2B2JS'
                'ZK2YZFJAyEek8si53jhYQEmaRq1zPfGbX84B2FJ8v4iI%2FTC1'
                'I9OE5vHF0sWwIR9d73JDrFLjaync7QYFWRExdwvqlQX%2BPO3r'
                'OG9Ns%2BcQFIN7npnsVjH28yNY9gBzXya8LYmNvUx6bWHWZMiu'
                'fLwDZ0jejNeDZTOfQGRM%2B0vY7NslzaT06W1wo8P7McSkAZEl'
                'DCbhR0Vo1fturPMwmAhi88f0qzRzywbg%3D%3D')

    json_contents = pkgutil.get_data('gslib', 'tests/test_data/test.json')
    key, client_email = gslib.commands.signurl._ReadJSONKeystore(
        json_contents)

    expiration = 0
    signed_url = gslib.commands.signurl._GenSignedUrl(
        key, client_email, 'GET', '', '', expiration, 'test/test.txt',
        self.logger)
    self.assertEquals(expected, signed_url)
