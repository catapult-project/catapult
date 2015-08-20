# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import tempfile
import unittest

from tracing_build import trace2html


class Trace2HTMLTests(unittest.TestCase):

  def test_writeHTMLForTracesToFile(self):
    pass