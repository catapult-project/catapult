# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.value import summary as summary_module

class OutputFormatter(object):
  """A formatter for PageTestResults.

  An OutputFormatter takes PageTestResults, formats the results
  (telemetry.value.Value instances), and output the formatted results
  in the given output stream.

  Examples of output formatter: CsvOutputFormatter produces results in
  CSV format."""

  def __init__(self, output_stream):
    """Constructs a new formatter that writes to the output_stream.

    Args:
      output_stream: The stream to write the formatted output to.
    """
    self._output_stream = output_stream

  def Format(self, page_test_results):
    """Formats the given PageTestResults into the output stream.

    This will be called once at the end of a benchmark.

    Args:
      page_test_results: A PageTestResults object containing all results
         from the current benchmark run.
    """
    raise NotImplementedError()

  def PrintViewResults(self):
    print 'View result at file://' + os.path.abspath(self.output_stream.name)

  @property
  def output_stream(self):
    return self._output_stream


def SummarizePageSpecificValues(results):
  """Summarize results appropriately for TBM and legacy benchmarks.

  For benchmarks that are timeline-based, we need to summarize not once, but
  twice, once by name and grouping_label (default) and again by name only. But
  for benchmarks that are not timeline-based, we only summarize once by name.
  """
  # Default summary uses merge_values.DefaultKeyFunc to summarize both by name
  # and grouping_label.
  summary = summary_module.Summary(results)
  values = summary.interleaved_computed_per_page_values_and_summaries

  if any(v.grouping_label for v in results.IterAllLegacyValues()):
    summary_by_name_only = summary_module.Summary(
        results, key_func=lambda v: v.name)
    values.extend(
        summary_by_name_only.interleaved_computed_per_page_values_and_summaries
    )
  return values
