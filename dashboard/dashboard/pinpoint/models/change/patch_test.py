# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.change import patch


class PatchTest(unittest.TestCase):

  def testPatch(self):
    p = patch.Patch('https://codereview.chromium.org', 2851943002, 40001)

    other_patch = patch.Patch(u'https://codereview.chromium.org',
                              2851943002, 40001)
    self.assertEqual(p, other_patch)
    string = 'https://codereview.chromium.org/2851943002/40001'
    self.assertEqual(str(p), string)
    self.assertEqual(p.id_string, string)

  def testAsDict(self):
    p = patch.Patch('https://codereview.chromium.org', 2851943002, 40001)
    expected = {
        'server': 'https://codereview.chromium.org',
        'issue': 2851943002,
        'patchset': 40001,
    }
    self.assertEqual(p.AsDict(), expected)

  def testFromDict(self):
    p = patch.Patch.FromDict({
        'server': 'https://codereview.chromium.org',
        'issue': 2851943002,
        'patchset': 40001,
    })

    expected = patch.Patch('https://codereview.chromium.org', 2851943002, 40001)
    self.assertEqual(p, expected)
