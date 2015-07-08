# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest
import tempfile
import shutil
import sys

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing.build import generate_about_tracing_contents


class GenerateAboutTracingContentsUnittTest(unittest.TestCase):

  def test_smokeTest(self):
    try:
      tmpdir = tempfile.mkdtemp()
      res = generate_about_tracing_contents.main(['--outdir', tmpdir])
      assert res == 0
    finally:
      shutil.rmtree(tmpdir)
