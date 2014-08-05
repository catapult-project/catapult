# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.results import output_formatter

def ResultsAsDict(res, metadata):
  result_dict = {
    'format_version': '0.2',
    'benchmark_name': metadata.name,
    'summary_values': [v.AsDict() for v in res.all_summary_values],
    'per_page_values': [v.AsDict() for v in res.all_page_specific_values],
    'pages': dict((p.id, p.AsDict()) for p in _all_pages(res))
  }

  return result_dict

def _all_pages(res):
  pages = set(page_run.page for page_run in res.all_page_runs)
  return pages

class JsonOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, metadata):
    super(JsonOutputFormatter, self).__init__(output_stream)
    self._metadata = metadata

  @property
  def metadata(self):
    return self._metadata

  def Format(self, page_test_results):
    json.dump(ResultsAsDict(page_test_results, self.metadata),
        self.output_stream)
    self.output_stream.write('\n')
