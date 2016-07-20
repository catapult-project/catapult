# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import StringIO
import json
import unittest
import os
import tempfile

from tracing import results_renderer


# Wrap string IO with a .name property so that it behaves more like a file.
class StringIOFile(StringIO.StringIO):
  name = 'fake_output_file'


class ResultsRendererTest(unittest.TestCase):

  def setUp(self):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    self.output_file = tmp.name
    self.output_stream = codecs.open(self.output_file,
                                     mode='r+',
                                     encoding='utf-8')

  def GetOutputFileContent(self):
    self.output_stream.seek(0)
    return self.output_stream.read()

  def tearDown(self):
    os.remove(self.output_file)

  def testBasic(self):
    value0 = {'foo': 0}
    value0_json = json.dumps(value0, separators=(',', ':'))

    results_renderer.RenderHTMLView([], self.output_stream, False)
    self.assertEquals([],
                      results_renderer.ReadExistingResults(self.output_stream))
    results_renderer.RenderHTMLView([value0], self.output_stream, False)
    self.assertEquals(
        sorted([value0]),
        sorted(results_renderer.ReadExistingResults(self.output_stream)))
    self.assertIn(value0_json, self.GetOutputFileContent())

  def testExistingResults(self):
    value0 = {'foo': 0}
    value0_json = json.dumps(value0, separators=(',', ':'))

    value1 = {'bar': 1}
    value1_json = json.dumps(value1, separators=(',', ':'))

    results_renderer.RenderHTMLView([value0], self.output_stream, False)
    results_renderer.RenderHTMLView([value1], self.output_stream, False)
    self.assertEquals(
        sorted([value0, value1]),
        sorted(results_renderer.ReadExistingResults(self.output_stream)))
    self.assertIn(value0_json, self.GetOutputFileContent())
    self.assertIn(value1_json, self.GetOutputFileContent())

  def testExistingResultsReset(self):
    value0 = {'foo': 0}
    value0_json = json.dumps(value0, separators=(',', ':'))

    value1 = {'bar': 1}
    value1_json = json.dumps(value1, separators=(',', ':'))

    results_renderer.RenderHTMLView([value0], self.output_stream, False)
    results_renderer.RenderHTMLView([value1], self.output_stream, True)
    self.assertEquals(
        sorted([value1]),
        sorted(results_renderer.ReadExistingResults(self.output_stream)))
    self.assertNotIn(value0_json, self.GetOutputFileContent())
    self.assertIn(value1_json, self.GetOutputFileContent())
