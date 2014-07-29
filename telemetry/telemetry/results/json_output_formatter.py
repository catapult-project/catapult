# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.results import output_formatter

def ResultsAsDict(res):
  result_dict = {
    'format_version': '0.1',
    'summary_values': [v.AsDict() for v in res.all_summary_values],
    'per_page_values': [v.AsDict() for v in res.all_page_specific_values],
    'pages': dict((p.id, p.AsDict()) for p in _all_pages(res))
  }

  return result_dict

def _all_pages(res):
  pages = set(value.page for value in res.all_page_specific_values)
  return pages

class JsonOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream):
    super(JsonOutputFormatter, self).__init__(output_stream)

  def Format(self, page_test_results):
    json.dump(ResultsAsDict(page_test_results), self.output_stream)
    self.output_stream.write('\n')
