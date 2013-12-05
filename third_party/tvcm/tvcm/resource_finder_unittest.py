#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for resource_finder."""

import os
import unittest

import module
import resource_finder

SRC_DIR = os.path.join(os.path.dirname(__file__), '../../../src')


class ResourceFinderTest(unittest.TestCase):

  def test_basic(self):
    finder = resource_finder.ResourceFinder([SRC_DIR])
    guid_module = module.Module('guid')
    guid_module.load_and_parse(os.path.join(SRC_DIR, 'base', 'guid.js'))
    filename, contents = finder.find_and_load_module(guid_module, 'base')

    self.assertTrue(os.path.samefile(filename,
                                     os.path.join(SRC_DIR, 'base.js')))
    expected_contents = ''
    with open(os.path.join(SRC_DIR, 'base.js')) as f:
      expected_contents = f.read()
    self.assertEquals(contents, expected_contents)

  def test_dependency_in_subdir(self):
    finder = resource_finder.ResourceFinder([SRC_DIR])
    guid_module = module.Module('base.guid')
    guid_module.load_and_parse(os.path.join(SRC_DIR, 'base', 'guid.js'))
    filename, contents = finder.find_and_load_module(
        guid_module, 'tracing.tracks.track')

    assert filename

    self.assertTrue(os.path.samefile(filename, os.path.join(
      SRC_DIR, 'tracing', 'tracks', 'track.js')))
    expected_contents = ''
    with open(os.path.join(SRC_DIR, 'tracing', 'tracks', 'track.js')) as f:
      expected_contents = f.read()
    self.assertEquals(contents, expected_contents)


if __name__ == '__main__':
  unittest.main()
