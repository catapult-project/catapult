# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.change import patch
from dashboard.pinpoint import test



def Patch(revision='abc123'):
  return patch.GerritPatch('https://codereview.com', 'repo~branch~id', revision)


_GERRIT_CHANGE_INFO = {
    '_number': 658277,
    'id': 'repo~branch~id',
    'project': 'chromium/src',
    'subject': 'Subject',
    'current_revision': 'current revision',
    'revisions': {
        'current revision': {
            '_number': 5,
            'created': '2018-02-01 23:46:56.000000000',
            'uploader': {'email': 'author@example.org'},
            'fetch': {
                'http': {
                    'url': 'https://googlesource.com/chromium/src',
                    'ref': 'refs/changes/77/658277/5',
                },
            },
        },
        'other revision': {
            '_number': 4,
            'created': '2018-02-01 23:46:56.000000000',
            'uploader': {'email': 'author@example.org'},
            'fetch': {
                'http': {
                    'url': 'https://googlesource.com/chromium/src',
                    'ref': 'refs/changes/77/658277/4',
                },
            },
        },
    },
}


class FromDictTest(test.TestCase):

  def setUp(self):
    super(FromDictTest, self).setUp()
    self.get_change.return_value = _GERRIT_CHANGE_INFO

  def testFromDictGerrit(self):
    p = patch.FromDict('https://codereview.com/c/repo/+/658277')
    self.assertEqual(p, Patch('current revision'))

  def testFromDictGerritWithRevision(self):
    p = patch.FromDict('https://codereview.com/c/repo/+/658277/4')
    self.assertEqual(p, Patch('other revision'))

  def testFromDictBadUrl(self):
    with self.assertRaises(ValueError):
      patch.FromDict('https://codereview.com/not/a/codereview/url')


class GerritPatchTest(test.TestCase):

  def setUp(self):
    super(GerritPatchTest, self).setUp()
    self.get_change.return_value = _GERRIT_CHANGE_INFO

  def testPatch(self):
    p = patch.GerritPatch('https://example.com', 'abcdef', '2f0d5c7')

    other_patch = patch.GerritPatch(u'https://example.com', 'abcdef', '2f0d5c7')
    self.assertEqual(p, other_patch)
    self.assertEqual(str(p), '2f0d5c7')
    self.assertEqual(p.id_string, 'https://example.com/abcdef/2f0d5c7')

  def testBuildParameters(self):
    p = Patch('current revision')
    expected = {
        'patch_gerrit_url': 'https://codereview.com',
        'patch_issue': 658277,
        'patch_project': 'chromium/src',
        'patch_ref': 'refs/changes/77/658277/5',
        'patch_repository_url': 'https://googlesource.com/chromium/src',
        'patch_set': 5,
        'patch_storage': 'gerrit',
    }
    self.assertEqual(p.BuildParameters(), expected)

  def testAsDict(self):
    p = Patch('current revision')
    expected = {
        'server': 'https://codereview.com',
        'change': 'repo~branch~id',
        'revision': 'current revision',
        'url': 'https://codereview.com/c/chromium/src/+/658277/5',
        'subject': 'Subject',
        'author': 'author@example.org',
        'time': '2018-02-01 23:46:56.000000000',
    }
    self.assertEqual(p.AsDict(), expected)

  def testFromDict(self):
    p = patch.GerritPatch.FromDict({
        'server': 'https://codereview.com',
        'change': 658277,
        'revision': 4,
    })
    self.assertEqual(p, Patch('other revision'))

  def testFromDictString(self):
    p = patch.GerritPatch.FromDict('https://codereview.com/c/repo/+/658277')
    self.assertEqual(p, Patch('current revision'))

  def testFromDictStringWithHash(self):
    p = patch.GerritPatch.FromDict('https://codereview.com/#/c/repo/+/658277')
    self.assertEqual(p, Patch('current revision'))
