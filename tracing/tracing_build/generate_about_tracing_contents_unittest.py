# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import shutil
import sys
import tempfile

if sys.version_info < (3,):
  from tracing_build import generate_about_tracing_contents


@unittest.skipIf(sys.version_info >= (3,),
                 'py_vulcanize is not ported to python3')
class GenerateAboutTracingContentsUnittTest(unittest.TestCase):

  def testSmoke(self):
    try:
      tmpdir = tempfile.mkdtemp()
      res = generate_about_tracing_contents.Main(['--outdir', tmpdir])
      assert res == 0
    finally:
      shutil.rmtree(tmpdir)
