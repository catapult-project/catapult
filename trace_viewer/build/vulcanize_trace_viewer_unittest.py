# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import tempfile
import os

from trace_viewer.build import vulcanize_trace_viewer
from tvcm import generate

class Trace2HTMLTests(unittest.TestCase):
  def test_writeHTMLForTracesToFile(self):
    can_minify=generate.CanMinify()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html') as tmpfile:
      res = vulcanize_trace_viewer.WriteTraceViewer(tmpfile, minify=can_minify)
