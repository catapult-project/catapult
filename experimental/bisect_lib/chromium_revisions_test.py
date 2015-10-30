# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import unittest

_EXPERIMENTAL = os.path.join(os.path.dirname(__file__), os.pardir)
_CATAPULT = os.path.join(_EXPERIMENTAL, os.pardir)

# TODO(robertocn): Add these to sys.path conditionally.
sys.path.append(os.path.join(_CATAPULT, 'third_party', 'mock'))
sys.path.append(_EXPERIMENTAL)

import mock

from bisect_lib import chromium_revisions


FIRST_REVISION = '53fc07eb478520a80af6bf8b62be259bb55db0f1'
LAST_REVISION = 'c89130e28fd01062104e1be7f3a6fc3abbb80ca9'

TEST_DATA_LOCATION = os.path.join(os.path.dirname(__file__),
                                  'test_data')
MOCK_INFO_RESPONSE_FILE = open(os.path.join(
    TEST_DATA_LOCATION, 'MOCK_INFO_RESPONSE_FILE'))
MOCK_RANGE_RESPONSE_FILE = open(os.path.join(
    TEST_DATA_LOCATION, 'MOCK_RANGE_RESPONSE_FILE'))

EXPECTED_INFO = {
    'body':
        'BUG=548160',
    'date':
        'Tue Oct 27 21:26:30 2015',
    'subject':
        '[Extensions] Fix hiding browser actions without the toolbar redesign',
    'email':
        'rdevlin.cronin@chromium.org',
    'author':
        'rdevlin.cronin'
}

INTERVENING_REVISIONS = [
    '2e93263dc74f0496100435e1fd7232e9e8323af0',
    '6feaa73a54d0515ad2940709161ca0a5ad91d1f8',
    '3861789af25e2d3502f0fb7080da5785d31308aa',
    '8fcc8af20a3d41b0512e3b1486e4dc7de528a72b',
    'f1c777e3f97a16cc6a3aa922a23602fa59412989',
    'ee261f306c3c66e96339aa1026d62a6d953302fe',
    '7bd1741893bd4e233b5562a6926d7e395d558343',
    '4f81be50501fbc02d7e44df0d56032e5885e19b6',
    '8414732168a8867a5d6bd45eaade68a5820a9e34',
    '01542ac6d0fbec6aa78e33e6c7ec49a582072ea9',
    '66aeb2b7084850d09f3fccc7d7467b57e4da1882',
    '48c1471f1f503246dd66753a4c7588d77282d2df',
    '84f6037e951c21a3b00bd3ddd034f258da6839b5',
    'ebd5f102ee89a4be5c98815c02c444fbf2b6b040',
    '5dbc149bebecea186b693b3d780b6965eeffed0f',
    '22e49fb496d6ffa122c470f6071d47ccb4ccb672',
    '07a6d9854efab6677b880defa924758334cfd47d',
    '32ce3b13924d84004a3e05c35942626cbe93cbbd',
]


class ChromiumRevisionsTest(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

  def testRevisionInfo(self):
    with mock.patch('urllib2.urlopen', mock.MagicMock(
        return_value=MOCK_INFO_RESPONSE_FILE)):
      test_info = chromium_revisions.revision_info(LAST_REVISION)
    for key in EXPECTED_INFO:
      self.assertIn(EXPECTED_INFO[key], test_info[key])

  def testRevisionRange(self):
    with mock.patch('urllib2.urlopen', mock.MagicMock(
        return_value=MOCK_RANGE_RESPONSE_FILE)):
      rev_list = chromium_revisions.revision_range(
          FIRST_REVISION, LAST_REVISION)
    commits_only = [entry['commit'] for entry in rev_list]
    for r in INTERVENING_REVISIONS:
      self.assertIn(r, commits_only)
    self.assertIn(LAST_REVISION, commits_only)
    self.assertEqual(len(INTERVENING_REVISIONS) + 1,
                     len(rev_list))

if __name__ == '__main__':
  unittest.main()

