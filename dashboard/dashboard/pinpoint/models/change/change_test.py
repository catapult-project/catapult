# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dashboard.pinpoint.models.change import change
from dashboard.pinpoint.models.change import commit
from dashboard.pinpoint.models.change import commit_test
from dashboard.pinpoint.models.change import patch as patch_module
from dashboard.pinpoint import test


_PATCH = patch_module.GerritPatch(
    'https://codereview.com', 'repo~branch~id', '2f0d5c7')


def Change(chromium=None, catapult=None, another_repo=None, patch=None):
  commits = []
  if chromium is not None:
    commits.append(commit_test.Commit(chromium))
  if catapult is not None:
    commits.append(commit_test.Commit(catapult, repository='catapult'))
  if another_repo is not None:
    commits.append(commit_test.Commit(another_repo, repository='another_repo'))
  return change.Change(commits, patch=patch)


class ChangeTest(test.TestCase):

  def testChange(self):
    base_commit = commit.Commit('chromium', 'aaa7336c821888839f759c6c0a36b56c')
    dep = commit.Commit('catapult', 'e0a2efbb3d1a81aac3c90041eefec24f066d26ba')

    # Also test the deps conversion to tuple.
    c = change.Change([base_commit, dep], _PATCH)

    self.assertEqual(c, change.Change((base_commit, dep), _PATCH))
    string = 'chromium@aaa7336 catapult@e0a2efb + 2f0d5c7'
    id_string = ('catapult@e0a2efbb3d1a81aac3c90041eefec24f066d26ba '
                 'chromium@aaa7336c821888839f759c6c0a36b56c + '
                 'https://codereview.com/repo~branch~id/2f0d5c7')
    self.assertEqual(str(c), string)
    self.assertEqual(c.id_string, id_string)
    self.assertEqual(c.base_commit, base_commit)
    self.assertEqual(c.last_commit, dep)
    self.assertEqual(c.deps, (dep,))
    self.assertEqual(c.commits, (base_commit, dep))
    self.assertEqual(c.patch, _PATCH)

  def testUpdate(self):
    old_commit = commit.Commit('chromium', 'aaaaaaaa')
    dep_a = commit.Commit('catapult', 'e0a2efbb')
    change_a = change.Change((old_commit, dep_a))

    new_commit = commit.Commit('chromium', 'bbbbbbbb')
    dep_b = commit.Commit('another_repo', 'e0a2efbb')
    change_b = change.Change((dep_b, new_commit), _PATCH)

    expected = change.Change((new_commit, dep_a, dep_b), _PATCH)
    self.assertEqual(change_a.Update(change_b), expected)

  def testUpdateWithMultiplePatches(self):
    c = Change(chromium=123, patch=_PATCH)
    with self.assertRaises(NotImplementedError):
      c.Update(c)

  @mock.patch('dashboard.pinpoint.models.change.patch.GerritPatch.AsDict')
  def testAsDict(self, patch_as_dict):
    patch_as_dict.return_value = {'revision': '2f0d5c7'}

    c = Change(chromium=123, catapult=456, patch=_PATCH)

    expected = {
        'commits': [
            {
                'author': 'author@chromium.org',
                'commit_position': 123456,
                'git_hash': 'commit 123',
                'repository': 'chromium',
                'subject': 'Subject.',
                'time': 'Fri Jan 01 00:01:00 2018',
                'url': u'https://chromium.googlesource.com/chromium/src/+/commit 123',
            },
            {
                'author': 'author@chromium.org',
                'commit_position': 123456,
                'git_hash': 'commit 456',
                'repository': 'catapult',
                'subject': 'Subject.',
                'time': 'Fri Jan 01 00:01:00 2018',
                'url': u'https://chromium.googlesource.com/catapult/+/commit 456',
            },
        ],
        'patch': {'revision': '2f0d5c7'},
    }
    self.assertEqual(c.AsDict(), expected)

  def testFromDictWithJustOneCommit(self):
    c = change.Change.FromDict({
        'commits': [{'repository': 'chromium', 'git_hash': 'commit 123'}],
    })
    self.assertEqual(c, Change(chromium=123))

  @mock.patch('dashboard.services.gerrit_service.GetChange')
  def testFromDictWithAllFields(self, get_change):
    get_change.return_value = {
        'id': 'repo~branch~id',
        'revisions': {'2f0d5c7': {}}
    }

    c = change.Change.FromDict({
        'commits': (
            {'repository': 'chromium', 'git_hash': 'commit 123'},
            {'repository': 'catapult', 'git_hash': 'commit 456'},
        ),
        'patch': {
            'server': 'https://codereview.com',
            'change': 'repo~branch~id',
            'revision': '2f0d5c7',
        },
    })

    expected = Change(chromium=123, catapult=456, patch=_PATCH)
    self.assertEqual(c, expected)


class MidpointTest(test.TestCase):

  def setUp(self):
    super(MidpointTest, self).setUp()

    def _FileContents(repository_url, git_hash, path):
      del path
      if repository_url != test.CHROMIUM_URL:
        return 'deps = {}'
      if int(git_hash.split()[1]) <= 4:  # DEPS roll at chromium@5
        return 'deps = {"chromium/catapult": "%s@commit 0"}' % (
            test.CATAPULT_URL + '.git')
      else:
        return 'deps = {"chromium/catapult": "%s@commit 9"}' % test.CATAPULT_URL
    self.file_contents.side_effect = _FileContents

  def testDifferingPatch(self):
    with self.assertRaises(commit.NonLinearError):
      change.Change.Midpoint(Change(0), Change(2, patch=_PATCH))

  def testDifferingRepository(self):
    with self.assertRaises(commit.NonLinearError):
      change.Change.Midpoint(Change(0), Change(another_repo=123))

  def testDifferingCommitCount(self):
    with self.assertRaises(commit.NonLinearError):
      change.Change.Midpoint(Change(0), Change(9, another_repo=123))

  def testSameChange(self):
    with self.assertRaises(commit.NonLinearError):
      change.Change.Midpoint(Change(0), Change(0))

  def testAdjacentWithNoDepsRoll(self):
    with self.assertRaises(commit.NonLinearError):
      change.Change.Midpoint(Change(0), Change(1))

  def testAdjacentWithDepsRoll(self):
    midpoint = change.Change.Midpoint(Change(4), Change(5))
    self.assertEqual(midpoint, Change(4, catapult=4))

  def testNotAdjacent(self):
    midpoint = change.Change.Midpoint(Change(0), Change(9))
    self.assertEqual(midpoint, Change(4))

  def testDepsRollLeft(self):
    midpoint = change.Change.Midpoint(Change(4), Change(4, catapult=4))
    self.assertEqual(midpoint, Change(4, catapult=2))

  def testDepsRollRight(self):
    midpoint = change.Change.Midpoint(Change(4, catapult=4), Change(5))
    self.assertEqual(midpoint, Change(4, catapult=6))

  def testAdjacentWithDepsRollAndDepAlreadyOverridden(self):
    midpoint = change.Change.Midpoint(Change(4), Change(5, catapult=4))
    self.assertEqual(midpoint, Change(4, catapult=2))
