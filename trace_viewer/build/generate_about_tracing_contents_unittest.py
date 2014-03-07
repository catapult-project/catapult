# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import unittest
import tempfile
import shutil

from trace_viewer.build import generate_about_tracing_contents

class GenerateAboutTracingContentsUnittTest(unittest.TestCase):
  def test_smokeTest(self):
    try:
      tmpdir = tempfile.mkdtemp()
      res = generate_about_tracing_contents.main(['--outdir', tmpdir])
      assert res == 0
    finally:
      shutil.rmtree(tmpdir)
