# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import tempfile
import os

from build import trace2html

class Trace2HTMLTests(unittest.TestCase):
  def test_smokeTest(self):
    try:
      tmpfile = tempfile.NamedTemporaryFile()
      big_trace_path = os.path.join(os.path.dirname(__file__),
                                    '..', 'test_data', 'big_trace.json')
      res = trace2html.Main(
          ['--output', tmpfile.name, big_trace_path])
      assert res == 0
    finally:
      tmpfile.close()
