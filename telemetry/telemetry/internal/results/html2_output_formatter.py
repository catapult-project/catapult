# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.results import output_formatter

from tracing import results_renderer


class Html2OutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, metadata, reset_results):
    super(Html2OutputFormatter, self).__init__(output_stream)
    self._metadata = metadata
    self._reset_results = reset_results

  def Format(self, page_test_results):
    histograms = page_test_results.AsHistogramDicts(self._metadata)
    results_renderer.RenderHTMLView(histograms,
        self._output_stream, self._reset_results)
