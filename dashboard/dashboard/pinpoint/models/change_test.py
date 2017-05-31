# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from dashboard.pinpoint.models import change


class ChangeTest(unittest.TestCase):

  def setUp(self):
    patcher = mock.patch('dashboard.common.namespaced_stored_object.Get')
    self.addCleanup(patcher.stop)
    get = patcher.start()
    get.return_value = {
        'catapult': {
            'repository_url': 'https://chromium.googlesource.com/'
                              'external/github.com/catapult-project/catapult'
        },
        'src': {
            'repository_url': 'https://chromium.googlesource.com/chromium/src'
        },
    }

  def testChange(self):
    base_commit = change.Dep('src', 'aaa7336')
    dep = change.Dep('catapult', 'e0a2efb')
    patch = change.Patch('https://codereview.chromium.org', 2565263002, 20001)

    # Also test the deps conversion to frozenset.
    c = change.Change(base_commit, [dep], patch)

    self.assertEqual(c, change.Change(base_commit, (dep,), patch))
    string = ('src@aaa7336 catapult@e0a2efb + '
              'https://codereview.chromium.org/2565263002/20001')
    self.assertEqual(str(c), string)
    self.assertEqual(c.base_commit, base_commit)
    self.assertEqual(c.deps, frozenset((dep,)))
    self.assertEqual(c.all_deps, (base_commit, dep))
    self.assertEqual(c.patch, patch)

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  def testFromDictWithJustBaseCommit(self, _):
    c = change.Change.FromDict({
        'base_commit': {'repository': 'src', 'git_hash': 'aaa7336'},
    })

    expected = change.Change(change.Dep('src', 'aaa7336'))
    self.assertEqual(c, expected)

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  def testFromDictWithAllFields(self, _):
    c = change.Change.FromDict({
        'base_commit': {'repository': 'src', 'git_hash': 'aaa7336'},
        'deps': ({'repository': 'catapult', 'git_hash': 'e0a2efb'},),
        'patch': {
            'server': 'https://codereview.chromium.org',
            'issue': 2565263002,
            'patchset': 20001,
        },
    })

    base_commit = change.Dep('src', 'aaa7336')
    deps = (change.Dep('catapult', 'e0a2efb'),)
    patch = change.Patch('https://codereview.chromium.org', 2565263002, 20001)
    expected = change.Change(base_commit, deps, patch)
    self.assertEqual(c, expected)

  @mock.patch('dashboard.services.gitiles_service.CommitRange')
  def testMidpointSuccess(self, commit_range):
    commit_range.return_value = [
        {'commit': 'babe852'},
        {'commit': 'b57345e'},
        {'commit': '949b36d'},
        {'commit': '1ef4789'},
    ]

    change_a = change.Change(change.Dep('src', '0e57e2b'),
                             (change.Dep('catapult', 'e0a2efb'),))
    change_b = change.Change(change.Dep('src', 'babe852'),
                             (change.Dep('catapult', 'e0a2efb'),))
    self.assertEqual(change.Change.Midpoint(change_a, change_b),
                     change.Change(change.Dep('src', '949b36d'),
                                   (change.Dep('catapult', 'e0a2efb'),)))

  def testMidpointRaisesWithDifferingNumberOfDeps(self):
    change_a = change.Change(change.Dep('src', '0e57e2b'))
    change_b = change.Change(change.Dep('src', 'babe852'),
                             (change.Dep('catapult', 'e0a2efb'),))
    with self.assertRaises(change.NonLinearError):
      change.Change.Midpoint(change_a, change_b)

  def testMidpointRaisesWithDifferingPatch(self):
    change_a = change.Change(change.Dep('src', '0e57e2b'))
    change_b = change.Change(
        change.Dep('src', 'babe852'),
        patch=change.Patch('https://codereview.chromium.org', 2565263002, 20001))
    with self.assertRaises(change.NonLinearError):
      change.Change.Midpoint(change_a, change_b)

  def testMidpointRaisesWithDifferingRepository(self):
    change_a = change.Change(change.Dep('src', '0e57e2b'))
    change_b = change.Change(change.Dep('not_src', 'babe852'))
    with self.assertRaises(change.NonLinearError):
      change.Change.Midpoint(change_a, change_b)

  def testMidpointRaisesWithTheSameChange(self):
    c = change.Change(change.Dep('src', '0e57e2b'))
    with self.assertRaises(change.NonLinearError):
      change.Change.Midpoint(c, c)

  def testMidpointRaisesWithMultipleDifferingCommits(self):
    change_a = change.Change(change.Dep('src', '0e57e2b'),
                             (change.Dep('catapult', 'e0a2efb'),))
    change_b = change.Change(change.Dep('src', 'babe852'),
                             (change.Dep('catapult', 'bfa19de'),))
    with self.assertRaises(change.NonLinearError):
      change.Change.Midpoint(change_a, change_b)

  @mock.patch('dashboard.services.gitiles_service.CommitRange')
  def testMidpointReturnsNoneWithAdjacentCommits(self, commit_range):
    commit_range.return_value = [{'commit': 'b57345e'}]

    change_a = change.Change(change.Dep('src', '949b36d'))
    change_b = change.Change(change.Dep('src', 'b57345e'))
    self.assertIsNone(change.Change.Midpoint(change_a, change_b))


class DepTest(unittest.TestCase):

  def setUp(self):
    patcher = mock.patch('dashboard.common.namespaced_stored_object.Get')
    self.addCleanup(patcher.stop)
    get = patcher.start()
    get.return_value = {
        'src': {
            'repository_url': 'https://chromium.googlesource.com/chromium/src'
        }
    }

  def testDep(self):
    dep = change.Dep('src', 'aaa7336')

    self.assertEqual(dep, change.Dep('src', 'aaa7336'))
    self.assertEqual(str(dep), 'src@aaa7336')
    self.assertEqual(dep.repository, 'src')
    self.assertEqual(dep.git_hash, 'aaa7336')
    self.assertEqual(dep.repository_url,
                     'https://chromium.googlesource.com/chromium/src')

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  def testFromDict(self, _):
    dep = change.Dep.FromDict({
        'repository': 'src',
        'git_hash': 'aaa7336',
    })

    expected = change.Dep('src', 'aaa7336')
    self.assertEqual(dep, expected)

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  def testFromDictWithRepositoryUrl(self, _):
    dep = change.Dep.FromDict({
        'repository': 'https://chromium.googlesource.com/chromium/src',
        'git_hash': 'aaa7336',
    })

    expected = change.Dep('src', 'aaa7336')
    self.assertEqual(dep, expected)

  def testFromDictFailureFromUnknownRepo(self):
    with self.assertRaises(KeyError):
      change.Dep.FromDict({
          'repository': 'unknown repo',
          'git_hash': 'git hash',
      })

  @mock.patch('dashboard.services.gitiles_service.CommitInfo')
  def testFromDictFailureFromUnknownCommit(self, commit_info):
    commit_info.side_effect = KeyError()

    with self.assertRaises(KeyError):
      change.Dep.FromDict({
          'repository': 'src',
          'git_hash': 'unknown git hash',
      })

  @mock.patch('dashboard.services.gitiles_service.CommitRange')
  def testMidpointSuccess(self, commit_range):
    commit_range.return_value = [
        {'commit': 'babe852'},
        {'commit': 'b57345e'},
        {'commit': '949b36d'},
        {'commit': '1ef4789'},
    ]

    dep_a = change.Dep('src', '0e57e2b')
    dep_b = change.Dep('src', 'babe852')
    self.assertEqual(change.Dep.Midpoint(dep_a, dep_b),
                     change.Dep('src', '949b36d'))

  def testMidpointRaisesWithDifferingRepositories(self):
    dep_a = change.Dep('src', '0e57e2b')
    dep_b = change.Dep('not_src', 'babe852')

    with self.assertRaises(ValueError):
      change.Dep.Midpoint(dep_a, dep_b)

  @mock.patch('dashboard.services.gitiles_service.CommitRange')
  def testMidpointReturnsNoneWithAdjacentCommits(self, commit_range):
    commit_range.return_value = [{'commit': 'b57345e'}]

    dep_a = change.Dep('src', '949b36d')
    dep_b = change.Dep('src', 'b57345e')
    self.assertIsNone(change.Dep.Midpoint(dep_a, dep_b))

  @mock.patch('dashboard.services.gitiles_service.CommitRange')
  def testMidpointReturnsNoneWithEmptyRange(self, commit_range):
    commit_range.return_value = []

    dep_b = change.Dep('src', 'b57345e')
    dep_a = change.Dep('src', '949b36d')
    self.assertIsNone(change.Dep.Midpoint(dep_a, dep_b))


class PatchTest(unittest.TestCase):

  def testPatch(self):
    patch = change.Patch('https://codereview.chromium.org', 2851943002, 40001)

    string = 'https://codereview.chromium.org/2851943002/40001'
    self.assertEqual(str(patch), string)

  def testFromDict(self):
    patch = change.Patch.FromDict({
        'server': 'https://codereview.chromium.org',
        'issue': 2851943002,
        'patchset': 40001,
    })

    expected = change.Patch('https://codereview.chromium.org',
                            2851943002, 40001)
    self.assertEqual(patch, expected)
