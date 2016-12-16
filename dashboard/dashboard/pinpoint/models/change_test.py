# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models import change


class ChangeTest(unittest.TestCase):

  def testChange(self):
    base_commit = change.Dep('chromium/src', 'aaa7336c')
    dep = change.Dep('external/github.com/catapult-project/catapult', 'e0a2efb')
    patch = 'patch/rietveld/codereview.chromium.org/2565263002/20001'

    c = change.Change(base_commit, [dep], patch)

    self.assertEqual(c.base_commit, base_commit)
    self.assertEqual(c.deps, (dep,))
    self.assertEqual(c.patch, patch)

  def testDep(self):
    dep = change.Dep('chromium/src', 'aaa7336c')

    self.assertEqual(dep.repository, 'chromium/src')
    self.assertEqual(dep.git_hash, 'aaa7336c')
