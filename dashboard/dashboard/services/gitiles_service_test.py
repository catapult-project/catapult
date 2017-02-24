# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock

from google.appengine.api import urlfetch

from dashboard.services import gitiles_service


@mock.patch('google.appengine.api.urlfetch.fetch')
class GitilesTest(unittest.TestCase):

  def testCommitInfo(self, mock_fetch):
    return_value = {
        'commit': 'commit_hash',
        'tree': 'tree_hash',
        'parents': ['parent_hash'],
        'author': {
            'name': 'username',
            'email': 'email@chromium.org',
            'time': 'Fri Jan 01 00:00:00 2016',
        },
        'committer': {
            'name': 'Commit bot',
            'email': 'commit-bot@chromium.org',
            'time': 'Fri Jan 01 00:01:00 2016',
        },
        'message': 'Subject.\n\nCommit message.',
        'tree_diff': [
            {
                'type': 'modify',
                'old_id': 'old_hash',
                'old_mode': 33188,
                'old_path': 'a/b/c.py',
                'new_id': 'new_hash',
                'new_mode': 33188,
                'new_path': 'a/b/c.py',
            },
        ],
    }
    _SetFetchReturnValues(mock_fetch, return_value)
    self.assertEqual(gitiles_service.CommitInfo('repo', 'commit_hash'),
                     return_value)
    mock_fetch.assert_called_once_with(
        'https://chromium.googlesource.com/repo/+/commit_hash?format=JSON')

  def testCommitRange(self, mock_fetch):
    return_value = {
        'log': [
            {
                'commit': 'commit_2_hash',
                'tree': 'tree_2_hash',
                'parents': ['parent_2_hash'],
                'author': {
                    'name': 'username',
                    'email': 'email@chromium.org',
                    'time': 'Sat Jan 02 00:00:00 2016',
                },
                'committer': {
                    'name': 'Commit bot',
                    'email': 'commit-bot@chromium.org',
                    'time': 'Sat Jan 02 00:01:00 2016',
                },
                'message': 'Subject.\n\nCommit message.',
            },
            {
                'commit': 'commit_1_hash',
                'tree': 'tree_1_hash',
                'parents': ['parent_1_hash'],
                'author': {
                    'name': 'username',
                    'email': 'email@chromium.org',
                    'time': 'Fri Jan 01 00:00:00 2016',
                },
                'committer': {
                    'name': 'Commit bot',
                    'email': 'commit-bot@chromium.org',
                    'time': 'Fri Jan 01 00:01:00 2016',
                },
                'message': 'Subject.\n\nCommit message.',
            },
        ],
    }
    _SetFetchReturnValues(mock_fetch, return_value)
    self.assertEqual(
        gitiles_service.CommitRange('repo', 'commit_0_hash', 'commit_2_hash'),
        return_value['log'])
    mock_fetch.assert_called_once_with(
        'https://chromium.googlesource.com/repo/+log/'
        'commit_0_hash..commit_2_hash?format=JSON')

  def testCommitRangePaginated(self, mock_fetch):
    return_value_1 = {
        'log': [
            {'commit': 'commit_4_hash'},
            {'commit': 'commit_3_hash'},
        ],
        'next': 'commit_2_hash',
    }
    return_value_2 = {
        'log': [
            {'commit': 'commit_2_hash'},
            {'commit': 'commit_1_hash'},
        ],
    }

    _SetFetchReturnValues(mock_fetch, return_value_1, return_value_2)

    self.assertEqual(
        gitiles_service.CommitRange('repo', 'commit_0_hash', 'commit_4_hash'),
        return_value_1['log'] + return_value_2['log'])

  def testFileContents(self, mock_fetch):
    mock_fetch.return_value = mock.MagicMock(
        content='aGVsbG8=', status_code=200)
    self.assertEqual(
        gitiles_service.FileContents('repo', 'commit_hash', 'path'),
        'hello')
    mock_fetch.assert_called_once_with(
        'https://chromium.googlesource.com/repo/+/commit_hash/path?format=TEXT')

  def testRetries(self, mock_fetch):
    mock_fetch.side_effect = urlfetch.Error()
    with self.assertRaises(urlfetch.Error):
      gitiles_service.FileContents('repo', 'commit_hash', 'path')

    mock_fetch.side_effect = urlfetch.Error(), mock.MagicMock(
        content='aGVsbG8=', status_code=200)
    self.assertEqual(
        gitiles_service.FileContents('repo', 'commit_hash', 'path'),
        'hello')

    mock_fetch.side_effect = Exception(), mock.MagicMock(
        content='aGVsbG8=', status_code=200)
    with self.assertRaises(Exception):
      gitiles_service.FileContents('repo', 'commit_hash', 'path')

  def testNotFound(self, mock_fetch):
    mock_fetch.side_effect = gitiles_service.NotFoundError()
    with self.assertRaises(gitiles_service.NotFoundError):
      gitiles_service.FileContents('repo', 'commit_hash', 'path')

  def testCustomHostname(self, mock_fetch):
    mock_fetch.return_value = mock.MagicMock(
        content='aGVsbG8=', status_code=200)
    gitiles_service.FileContents('repo', 'commit_hash', 'path',
                                 hostname='https://example.com')
    mock_fetch.assert_called_once_with(
        'https://example.com/repo/+/commit_hash/path?format=TEXT')


def _SetFetchReturnValues(mock_fetch, *return_values):
  mock_fetch.side_effect = tuple(
      _MockifyReturnValue(return_value) for return_value in return_values)


def _MockifyReturnValue(return_value):
  return mock.MagicMock(content=")]}'\n" + json.dumps(return_value),
                        status_code=200)
