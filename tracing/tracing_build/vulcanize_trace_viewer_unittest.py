# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import sys
import unittest
import tempfile

if sys.version_info < (3,):
  from tracing_build import vulcanize_trace_viewer


@unittest.skipIf(sys.version_info >= (3,),
                 'py_vulcanize is not ported to python3')
class Trace2HTMLTests(unittest.TestCase):

  def testWriteHTMLForTracesToFile(self):
    try:
      # Note: We can't use "with" when working with tempfile.NamedTemporaryFile
      # as that does not work on Windows. We use the longer, more clunky version
      # instead. See https://bugs.python.org/issue14243 for detials.
      raw_tmpfile = tempfile.NamedTemporaryFile(
          mode='w', suffix='.html', delete=False)
      raw_tmpfile.close()
      with codecs.open(raw_tmpfile.name, 'w', encoding='utf-8') as tmpfile:
        vulcanize_trace_viewer.WriteTraceViewer(tmpfile)
    finally:
      os.remove(raw_tmpfile.name)
