# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import json
import unittest

from telemetry.internal.results import html2_output_formatter
from telemetry.internal.results import page_test_results


# Wrap string IO with a .name property so that it behaves more like a file.
class StringIOFile(StringIO.StringIO):
  name = 'fake_output_file'


class HtmlOutputFormatterTest(unittest.TestCase):
  def test_basic(self):
    output_file = StringIOFile()
    value0 = {'foo': 0}
    value1 = {'bar': 1}
    value2 = {'qux': 2}
    value0json = json.dumps(value0, separators=(',', ':'))
    value1json = json.dumps(value1, separators=(',', ':'))
    value2json = json.dumps(value2, separators=(',', ':'))

    def CreateFormatter(reset_results):
      return html2_output_formatter.Html2OutputFormatter(
              output_file, reset_results, False)

    def CreateResults(value):
      results = page_test_results.PageTestResults()
      results.value_set.append(value)
      return results

    # Run the first time and verify the results are written to the HTML file.
    results = CreateResults(value0)
    formatter = CreateFormatter(False)
    self.assertEquals([], formatter.values)
    formatter.Format(results)
    self.assertEquals([value0], formatter.values)
    self.assertIn(value0json, output_file.getvalue())

    # Run the second time and verify the results are appended to the HTML file.
    output_file.seek(0)
    results = CreateResults(value1)
    formatter = CreateFormatter(False)
    self.assertEquals([value0], formatter.values)
    formatter.Format(results)
    self.assertEquals([value0, value1], formatter.values)
    self.assertIn(value0json, output_file.getvalue())
    self.assertIn(value1json, output_file.getvalue())

    # Now reset the results and verify the old ones are gone.
    output_file.seek(0)
    results = CreateResults(value2)
    formatter = CreateFormatter(True)
    self.assertEquals([], formatter.values)
    formatter.Format(results)
    self.assertEquals([value2], formatter.values)
    self.assertNotIn(value0json, output_file.getvalue())
    self.assertNotIn(value1json, output_file.getvalue())
    self.assertIn(value2json, output_file.getvalue())
