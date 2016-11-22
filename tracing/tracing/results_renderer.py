# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import re

import tracing_project
from py_vulcanize import generate


# If you change this, please update "Fall-back to old formats."
_JSON_TAG = '<histogram-json>%s</histogram-json>'


def ExtractJSON(results_html, json_tag):
  results = []
  pattern = '(.*?)'.join(re.escape(part) for part in json_tag.split('%s'))
  flags = re.MULTILINE | re.DOTALL
  for match in re.finditer(pattern, results_html, flags):
    try:
      results.append(json.loads(match.group(1)))
    except ValueError:
      logging.warn('Found existing results json, but failed to parse it.')
      return []
  return results


def ReadExistingResults(results_html):
  if not results_html:
    return []

  histograms = ExtractJSON(results_html, _JSON_TAG)

  # Fall-back to old formats.
  if not histograms:
    histograms = ExtractJSON(
        results_html, json_tag='<div class="histogram-json">%s</div>')
  if not histograms:
    match = re.search('<div id="value-set-json">(.*?)</div>', results_html,
                      re.MULTILINE | re.DOTALL)
    if match:
      histograms = json.loads(match.group(1))

  if not histograms:
    logging.warn('Failed to extract previous results from HTML output')
  return histograms


def RenderHTMLView(histograms, output_stream, reset_results=False):
  output_stream.seek(0)

  if not reset_results:
    results_html = output_stream.read()
    output_stream.seek(0)
    histograms += ReadExistingResults(results_html)

  vulcanizer = tracing_project.TracingProject().CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(
      ['tracing.results2_template'])
  html = generate.GenerateStandaloneHTMLAsString(load_sequence)
  output_stream.write(html)

  output_stream.write('<div style="display:none;">')
  json_tag_newline = '\n%s' % _JSON_TAG
  for histogram in histograms:
    hist_json = json.dumps(histogram, separators=(',', ':'))
    output_stream.write(json_tag_newline % hist_json)
  output_stream.write('\n</div>\n')

  # If the output file already existed and was longer than the new contents,
  # discard the old contents after this point.
  output_stream.truncate()
