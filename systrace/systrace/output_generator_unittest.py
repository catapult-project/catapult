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
    t1 = {'traceEvents': [{'ts': 123, 'ph': 'b'}]}
    t2 = {'traceEvents': [], 'stackFrames': ['blah']}

    output_file_name1 = ''.join(random.choice(string.ascii_uppercase +
                            string.digits) for _ in range(10))
    output_file_name2 = ''.join(random.choice(string.ascii_uppercase +
                            string.digits) for _ in range(10))

    # Both trace files will be merged to a third file and will get deleted in
    # the process, so there's no need for NamedTemporaryFile to do the
    # deletion.
    with open(output_file_name1, 'wb') as f1:
      with open(output_file_name2, 'wb') as f2:
        f1.write(json.dumps(t1))
        f2.write(json.dumps(t2))
        f1.flush()
        f2.flush()

    output_files = output_generator.MergeTraceFilesIfNeeded(
                      [output_file_name1, output_file_name2])
    for output_file in output_files:
      with open(output_file) as f:
        output = json.load(f)
        self.assertEquals(output['traceEvents'], t1['traceEvents'])
        self.assertEquals(output['stackFrames'], t2['stackFrames'])
      if os.path.isfile(output_file):
        os.remove(output_file)

  @decorators.HostOnlyTest
  def testHtmlOutputGenerationFormatsSingleTrace(self):
    with open(ATRACE_DATA) as f:
      atrace_data = f.read().replace(" ", "").strip()
      trace_results = [trace_result.TraceResult('systemTraceEvents',
                       atrace_data)]
      output_file_name = ''.join(random.choice(string.ascii_uppercase +
                            string.digits) for _ in range(10))
      output_generator.GenerateHTMLOutput(trace_results, output_file_name)
      with open(output_file_name, 'r') as f:
        output_generator.GenerateHTMLOutput(trace_results, f.name)
        html_output = f.read()
        trace_data = (html_output.split(
          '<script class="trace-data" type="application/text">')[1].split(
          '</script>'))[0].replace(" ", "").strip()

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
    output_file_name = ''.join(random.choice(string.ascii_uppercase +
                            string.digits) for _ in range(10))
    output_generator.GenerateHTMLOutput(trace_results, output_file_name)
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
