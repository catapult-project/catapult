#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the parse_deps module."""

import os
import unittest

from tvcm import parse_deps

TVCM_DIR = os.path.join(os.path.dirname(__file__), '..')
THIRD_PARTY_DIR = os.path.join(os.path.dirname(__file__), '..', '..')

class CalcLoadSequenceTest(unittest.TestCase):
  def test_one_toplevel_nodeps(self):
    load_sequence = parse_deps.calc_load_sequence_internal(
        [os.path.join('base', 'guid.js')], [TVCM_DIR], [THIRD_PARTY_DIR])
    name_sequence = [x.name for x in load_sequence]
    self.assertEquals(['base.guid'], name_sequence)


if __name__ == '__main__':
  unittest.main()
