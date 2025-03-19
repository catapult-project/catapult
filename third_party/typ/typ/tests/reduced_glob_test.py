# Copyright 2025 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from typ import reduced_glob


class GlobUnittest(unittest.TestCase):

    def testMatchcaseGlob(self):
        """Tests supported behavior for matchcase."""
        g = lambda p: reduced_glob.ReducedGlob(p)

        # Exact match.
        self.assertTrue(g('test').matchcase('test'))
        # Exact match with starting glob.
        self.assertTrue(g('*test').matchcase('test'))
        # Exact match with trailing glob.
        self.assertTrue(g('test*').matchcase('test'))
        # Starting glob match.
        self.assertTrue(g('*foobar').matchcase('test_foobar'))
        # Trailing glob match.
        self.assertTrue(g('test_*').matchcase('test_foobar'))
        # Glob match in the middle.
        self.assertTrue(g('test*bar').matchcase('test_foobar'))
        # Glob match everything.
        self.assertTrue(g('*').matchcase('test_foobar'))
        # Multiple globs, starting ands trailing.
        self.assertTrue(g('*_*').matchcase('test_foobar'))
        # Multiple globs in the middle.
        self.assertTrue(g('t*f*r').matchcase('test_foobar'))
        # Case sensitivity.
        self.assertFalse(g('test*').matchcase('Test_foobar'))
        # Escaped glob.
        self.assertFalse(g('test_\\*').matchcase('test_.'))
        self.assertTrue(g('test_\\*').matchcase('test_*'))
        # Ensure there is no implicit starting glob.
        self.assertFalse(g('foobar').matchcase('test_foobar'))
        # Ensure there is no implicit trailing glob.
        self.assertFalse(g('test').matchcase('test_foobar'))

    def testMatchcaseUnsupportedWildcards(self):
        """Tests behavior when using unsupported wildcards."""
        # fnmatch supports '?', '[seq]', and '[!seq]' in addition to *, but
        # we intentionally do not want those to be special in this
        # implementation.

        # ?
        glob = reduced_glob.ReducedGlob('t?st')
        self.assertFalse(glob.matchcase('test'))
        self.assertTrue(glob.matchcase('t?st'))
        # [seq]
        glob = reduced_glob.ReducedGlob('t[ae]st')
        self.assertFalse(glob.matchcase('test'))
        self.assertTrue(glob.matchcase('t[ae]st'))
        # [!seq]
        glob = reduced_glob.ReducedGlob('t[!a]st')
        self.assertFalse(glob.matchcase('test'))
        self.assertTrue(glob.matchcase('t[!a]st'))
