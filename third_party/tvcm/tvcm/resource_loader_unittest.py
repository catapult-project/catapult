#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for resource_loader."""

import os
import unittest

import module
import resource_loader

TVCM_DIR = os.path.join(os.path.dirname(__file__), '..')
THIRD_PARTY_DIR = os.path.join(os.path.dirname(__file__), '..', '..')


class ResourceLoaderTest(unittest.TestCase):

  def test_basic(self):
    loader = resource_loader.ResourceLoader([TVCM_DIR], [THIRD_PARTY_DIR])
    guid_module = loader.load_module(module_name='base')
    self.assertTrue(os.path.samefile(guid_module.filename,
                                     os.path.join(TVCM_DIR, 'base', '__init__.js')))
    expected_contents = ''
    with open(os.path.join(TVCM_DIR, 'base', '__init__.js')) as f:
      expected_contents = f.read()
    self.assertEquals(guid_module.contents, expected_contents)

if __name__ == '__main__':
  unittest.main()
