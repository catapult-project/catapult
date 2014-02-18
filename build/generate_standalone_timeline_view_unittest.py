# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import tempfile
import shutil
import os

from build import generate_standalone_timeline_view

class GenerateStandaloneTimelineViewTests(unittest.TestCase):
  def test_smokeTest(self):
    try:
      tmpdir = tempfile.mkdtemp()
      js = os.path.join(tmpdir, 'timeline_view.js')
      css = os.path.join(tmpdir, 'timeline_view.css')
      res = generate_standalone_timeline_view.main(
          ['--js', js, '--css', css])
      assert res == 0
    finally:
      shutil.rmtree(tmpdir)
