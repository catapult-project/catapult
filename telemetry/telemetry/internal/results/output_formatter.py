# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


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

  @property
  def output_stream(self):
    return self._output_stream
