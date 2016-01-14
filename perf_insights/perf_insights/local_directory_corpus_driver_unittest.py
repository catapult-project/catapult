# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from perf_insights import local_directory_corpus_driver


class LocalDirectoryCorpusDriverTests(unittest.TestCase):

  def testTags(self):
    self.assertEquals(
        local_directory_corpus_driver._GetTagsForRelPath('a.json'), [])
    self.assertEquals(
        local_directory_corpus_driver._GetTagsForRelPath('/b/c/a.json'),
        ['b', 'c'])
