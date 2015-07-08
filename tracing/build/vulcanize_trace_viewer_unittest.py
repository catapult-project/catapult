# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import unittest
import tempfile

from tracing.build import vulcanize_trace_viewer


class Trace2HTMLTests(unittest.TestCase):
  def test_writeHTMLForTracesToFile(self):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html') as raw_tmpfile:
      with codecs.open(raw_tmpfile.name, 'w', encoding='utf-8') as tmpfile:
        vulcanize_trace_viewer.WriteTraceViewer(tmpfile)
