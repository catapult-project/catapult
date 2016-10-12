# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import re

import tracing_project
from py_vulcanize import generate


_JSON_TAG = '<div class="histogram-json">%s</div>'


def ReadExistingResults(output_stream):
  output_stream.seek(0)
  results_html = output_stream.read()
  if not results_html:
    return []
  histograms = []
  pattern = '(.*?)'.join(re.escape(part) for part in _JSON_TAG.split('%s'))
  flags = re.MULTILINE | re.DOTALL
  for match in re.finditer(pattern, results_html, flags):
    histograms.append(json.loads(match.group(1)))
  if not histograms:
    logging.warn('Failed to extract previous results from HTML output')
  return histograms


def RenderHTMLView(histograms, output_stream, reset_results=False):
  if not reset_results:
    histograms += ReadExistingResults(output_stream)
  output_stream.seek(0)

  vulcanizer = tracing_project.TracingProject().CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(
      ['tracing.results2_template'])
  html = generate.GenerateStandaloneHTMLAsString(load_sequence)
  output_stream.write(html)

  json_tag_newline = '\n%s' % _JSON_TAG
  for histogram in histograms:
    hist_json = json.dumps(histogram, separators=(',', ':'))
    output_stream.write(json_tag_newline % hist_json)
  output_stream.write('\n')

  # If the output file already existed and was longer than the new contents,
  # discard the old contents after this point.
  output_stream.truncate()
