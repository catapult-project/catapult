# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import StringIO
import unittest

from telemetry.internal.results import histogram_set_json_output_formatter


class HistogramSetJsonTest(unittest.TestCase):

  def setUp(self):
    self._output = StringIO.StringIO()
    self._formatter = (
        histogram_set_json_output_formatter.HistogramSetJsonOutputFormatter(
            self._output, reset_results=False))

  def testOutputAndParseDisabled(self):
    self._formatter.FormatDisabled(None)
    d = json.loads(self._output.getvalue())
    self.assertEquals(d, [])
