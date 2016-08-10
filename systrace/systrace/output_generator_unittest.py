#!/usr/bin/env python

# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import random
import string
import unittest

from systrace import decorators
from systrace import output_generator
from systrace import trace_result


TEST_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
ATRACE_DATA = os.path.join(TEST_DIR, 'atrace_data')
COMBINED_PROFILE_CHROME_DATA = os.path.join(
                                  TEST_DIR,
                                  'profile-chrome_systrace_perf_chrome_data')


class OutputGeneratorTest(unittest.TestCase):

  @decorators.HostOnlyTest
  def testJsonTraceMerging(self):
    t1 = "{'traceEvents': [{'ts': 123, 'ph': 'b'}]}"
    t2 = "{'traceEvents': [], 'stackFrames': ['blah']}"
    results = [trace_result.TraceResult('a', t1),
               trace_result.TraceResult('b', t2)]

    merged_results = output_generator.MergeTraceResultsIfNeeded(results)
    for r in merged_results:
      if r.source_name == 'a':
        self.assertEquals(r.raw_data, t1)
      elif r.source_name == 'b':
        self.assertEquals(r.raw_data, t2)
    self.assertEquals(len(merged_results), len(results))

  @decorators.HostOnlyTest
  def testHtmlOutputGenerationFormatsSingleTrace(self):
    with open(ATRACE_DATA) as f:
      atrace_data = f.read().replace(" ", "").strip()
      trace_results = [trace_result.TraceResult('systemTraceEvents',
                       atrace_data)]
      output_file_name = _GenerateRandomString(10)
      final_path = output_generator.GenerateHTMLOutput(trace_results,
                                                       output_file_name)
      with open(output_file_name, 'r') as f:
        output_generator.GenerateHTMLOutput(trace_results, f.name)
        html_output = f.read()
        trace_data = (html_output.split(
          '<script class="trace-data" type="application/text">')[1].split(
          '</script>'))[0].replace(" ", "").strip()
      os.remove(final_path)

    # Ensure the trace data written in HTML is located within the
    # correct place in the HTML document and that the data is not
    # malformed.
    self.assertEquals(trace_data, atrace_data)

  @decorators.HostOnlyTest
  def testHtmlOutputGenerationFormatsMultipleTraces(self):
    json_data = open(COMBINED_PROFILE_CHROME_DATA).read()
    combined_data = json.loads(json_data)
    trace_results = []
    trace_results_expected = []
    for (trace_name, data) in combined_data.iteritems():
      trace_results.append(trace_result.TraceResult(str(trace_name),
                                                    str(data)))
      trace_results_expected.append(str(data).replace(" ", "").strip())
    output_file_name = _GenerateRandomString(10)
    final_path = output_generator.GenerateHTMLOutput(trace_results,
                                                     output_file_name)
    with open(output_file_name, 'r') as f:
      html_output = f.read()
      for i in range(1, len(trace_results)):
        trace_data = (html_output.split(
          '<script class="trace-data" type="application/text">')[i].split(
          '</script>'))[0].replace(" ", "").strip()

        # Ensure the trace data written in HTML is located within the
        # correct place in the HTML document and that the data is not
        # malformed.
        self.assertTrue(trace_data in trace_results_expected)
    os.remove(final_path)

def _GenerateRandomString(strlen):
  return ''.join(random.choice(string.ascii_uppercase +
              string.digits) for _ in range(strlen))
