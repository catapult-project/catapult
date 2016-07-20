# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import re

import tracing_project
from py_vulcanize import generate


_JSON_TAG = '<div id="value-set-json">%s</div>'


def ReadExistingResults(output_stream):
  output_stream.seek(0)
  results_html = output_stream.read()
  if not results_html:
    return []
  m = re.search(_JSON_TAG % '(.*?)', results_html, re.MULTILINE
                | re.DOTALL)
  if not m:
    logging.warn('Failed to extract previous results from HTML output')
    return []
  return json.loads(m.group(1))


def RenderHTMLView(values, output_stream, reset_results=False):
  if not reset_results:
    values += ReadExistingResults(output_stream)
  vulcanizer = tracing_project.TracingProject().CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(
      ['tracing.results2_template'])
  html = generate.GenerateStandaloneHTMLAsString(load_sequence)
  html = html.replace(_JSON_TAG % '',
                      _JSON_TAG % json.dumps(values, separators=(',', ':')))
  output_stream.seek(0)
  output_stream.write(html)
  output_stream.truncate()
