# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import json
import os
import sys

from telemetry.internal.results import page_test_results


# List of formats supported by our legacy output formatters.
# TODO(crbug.com/981349): Should be eventually replaced entirely by the results
# processor in tools/perf.
LEGACY_OUTPUT_FORMATS = ('none')


def CreateResults(options, benchmark_name=None, benchmark_description=None,
                  report_progress=False):
  """
  Args:
    options: Contains the options specified in AddResultsOptions.
    benchmark_name: A string with the name of the currently running benchmark.
    benchmark_description: A string with a description of the currently
        running benchmark.
    report_progress: A boolean indicating whether to emit gtest style
        report of progress as story runs are being recorded.

  Returns:
    A PageTestResults object.
  """
  assert options.intermediate_dir, (
      'An intermediate_dir must be provided to create results')
  return page_test_results.PageTestResults(
      progress_stream=sys.stdout if report_progress else None,
      intermediate_dir=options.intermediate_dir,
      benchmark_name=benchmark_name,
      benchmark_description=benchmark_description,
      results_label=options.results_label)


def ReadTestResults(intermediate_dir):
  """Read results from an intermediate_dir into a single list."""
  results = []
  with open(os.path.join(
      intermediate_dir, page_test_results.TEST_RESULTS)) as f:
    for line in f:
      results.append(json.loads(line)['testResult'])
  return results


def ReadMeasurements(test_result):
  """Read ad hoc measurements recorded on a test result."""
  try:
    artifact = test_result['outputArtifacts']['measurements.json']
  except KeyError:
    return {}
  with open(artifact['filePath']) as f:
    return json.load(f)['measurements']
