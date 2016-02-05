# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import tempfile
import unittest

from tracing_build import trace2html


class Trace2HTMLTests(unittest.TestCase):

  def testWriteHTMLForTracesToFile(self):
    # Note: We can't use "with" when working with tempfile.NamedTemporaryFile as
    # that does not work on Windows. We use the longer, more clunky version
    # instead. See https://bugs.python.org/issue14243 for detials.
    raw_tmpfile = tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', delete=False)
    raw_tmpfile.close()
    try:
      with codecs.open(raw_tmpfile.name, 'w', encoding='utf-8') as tmpfile:
        simple_trace_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'test_data', 'simple_trace.json')
        big_trace_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'test_data', 'big_trace.json')
        non_json_trace_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'test_data', 'android_systrace.txt')
        trace2html.WriteHTMLForTracesToFile(
            [big_trace_path, simple_trace_path, non_json_trace_path], tmpfile)
    finally:
      os.remove(raw_tmpfile.name)
