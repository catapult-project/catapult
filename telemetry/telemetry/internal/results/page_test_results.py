# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import posixpath
import shutil
import tempfile
import time
import traceback

from telemetry import value as value_module
from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import html_output_formatter
from telemetry.internal.results import progress_reporter as reporter_module
from telemetry.internal.results import results_processor
from telemetry.internal.results import story_run

from tracing.value import convert_chart_json
from tracing.value import histogram_set
from tracing.value.diagnostics import all_diagnostics
from tracing.value.diagnostics import reserved_infos


class PageTestResults(object):
  def __init__(self, output_formatters=None, progress_reporter=None,
               output_dir=None, should_add_value=None, benchmark_name=None,
               benchmark_description=None, benchmark_enabled=True,
               upload_bucket=None, results_label=None):
    """
    Args:
      output_formatters: A list of output formatters. The output
          formatters are typically used to format the test results, such
          as CsvOutputFormatter, which output the test results as CSV.
      progress_reporter: An instance of progress_reporter.ProgressReporter,
          to be used to output test status/results progressively.
      output_dir: A string specifying the directory where to store the test
          artifacts, e.g: trace, videos, etc.
      should_add_value: A function that takes two arguments: a value name and
          a boolean (True when the value belongs to the first run of the
          corresponding story). It returns True if the value should be added
          to the test results and False otherwise.
      benchmark_name: A string with the name of the currently running benchmark.
      benchmark_description: A string with a description of the currently
          running benchmark.
      benchmark_enabled: A boolean indicating whether the benchmark to run
          is enabled. (Some output formats need to produce special output for
          disabled benchmarks).
      upload_bucket: A string identifting a cloud storage bucket where to
          upload artifacts.
      results_label: A string that serves as an identifier for the current
          benchmark run.
    """
    super(PageTestResults, self).__init__()
    self._progress_reporter = (
        progress_reporter if progress_reporter is not None
        else reporter_module.ProgressReporter())
    self._output_formatters = (
        output_formatters if output_formatters is not None else [])
    self._output_dir = output_dir
    self._upload_bucket = upload_bucket
    if should_add_value is not None:
      self._should_add_value = should_add_value
    else:
      self._should_add_value = lambda v, is_first: True

    self._current_story_run = None
    self._all_story_runs = []
    self._all_stories = set()
    self._representative_value_for_each_value_name = {}
    self._all_summary_values = []

    self._histograms = histogram_set.HistogramSet()

    self._benchmark_name = benchmark_name or '(unknown benchmark)'
    self._benchmark_description = benchmark_description or ''
    self._benchmark_start_us = time.time() * 1e6
    # |_interruption| is None if the benchmark has not been interrupted.
    # Otherwise it is a string explaining the reason for the interruption.
    # Interruptions occur for unrecoverable exceptions.
    self._interruption = None
    self._results_label = results_label

    # State of the benchmark this set of results represents.
    self._benchmark_enabled = benchmark_enabled

    self._histogram_dicts_to_add = []

  @property
  def benchmark_name(self):
    return self._benchmark_name

  @property
  def benchmark_description(self):
    return self._benchmark_description

  @property
  def benchmark_start_us(self):
    return self._benchmark_start_us

  @property
  def benchmark_interrupted(self):
    return bool(self._interruption)

  @property
  def benchmark_interruption(self):
    """Returns a string explaining why the benchmark was interrupted."""
    return self._interruption

  @property
  def label(self):
    return self._results_label

  @property
  def output_dir(self):
    return self._output_dir

  @property
  def upload_bucket(self):
    return self._upload_bucket

  def AsHistogramDicts(self):
    return self._histograms.AsDicts()

  def PopulateHistogramSet(self):
    if len(self._histograms):
      return

    # We ensure that html traces are serialized and uploaded if necessary
    results_processor.SerializeAndUploadHtmlTraces(self)

    chart_json = chart_json_output_formatter.ResultsAsChartDict(self)
    chart_json['label'] = self.label
    chart_json['benchmarkStartMs'] = self.benchmark_start_us / 1000.0

    file_descriptor, chart_json_path = tempfile.mkstemp()
    os.close(file_descriptor)
    json.dump(chart_json, file(chart_json_path, 'w'))

    vinn_result = convert_chart_json.ConvertChartJson(chart_json_path)

    os.remove(chart_json_path)

    if vinn_result.returncode != 0:
      logging.error('Error converting chart json to Histograms:\n' +
                    vinn_result.stdout)
      return []
    self._histograms.ImportDicts(json.loads(vinn_result.stdout))
    self._histograms.ImportDicts(self._histogram_dicts_to_add)

  @property
  def all_summary_values(self):
    return self._all_summary_values

  @property
  def current_page(self):
    """DEPRECATED: Use current_story instead."""
    return self.current_story

  @property
  def current_story(self):
    assert self._current_story_run, 'Not currently running test.'
    return self._current_story_run.story

  @property
  def current_story_run(self):
    return self._current_story_run

  @property
  def had_successes(self):
    """If there were any actual successes, not including skipped stories."""
    return any(run.ok for run in self._all_story_runs)

  @property
  def had_failures(self):
    """If there where any failed stories."""
    return any(run.failed for run in self._all_story_runs)

  @property
  def num_failed(self):
    """Number of failed stories."""
    return sum(1 for run in self._all_story_runs if run.failed)

  @property
  def had_skips(self):
    """If there where any skipped stories."""
    return any(run.skipped for run in self._IterAllStoryRuns())

  def _IterAllStoryRuns(self):
    # TODO(crbug.com/973837): Check whether all clients can just be switched
    # to iterate over _all_story_runs directly.
    for run in self._all_story_runs:
      yield run
    if self._current_story_run:
      yield self._current_story_run

  def IterStoryRuns(self):
    return iter(self._all_story_runs)

  def IterAllLegacyValues(self):
    for run in self._IterAllStoryRuns():
      for value in run.values:
        yield value

  def CloseOutputFormatters(self):
    """
    Clean up any open output formatters contained within this results object
    """
    for output_formatter in self._output_formatters:
      output_formatter.output_stream.close()

  def __enter__(self):
    return self

  def __exit__(self, _, __, ___):
    self.CloseOutputFormatters()

  def WillRunPage(self, page, story_run_index=0):
    assert not self._current_story_run, 'Did not call DidRunPage.'
    self._current_story_run = story_run.StoryRun(
        page, self._output_dir, story_run_index)
    self._progress_reporter.WillRunPage(self)

  def DidRunPage(self, page):  # pylint: disable=unused-argument
    """
    Args:
      page: The current page under test.
    """
    assert self._current_story_run, 'Did not call WillRunPage.'
    self._current_story_run.Finish()
    self._progress_reporter.DidRunPage(self)
    self._all_story_runs.append(self._current_story_run)
    story = self._current_story_run.story
    self._all_stories.add(story)
    self._current_story_run = None

  def AddMetricPageResults(self, result):
    """Add results from metric computation.

    Args:
      result: A dict produced by results_processor._ComputeMetricsInPool.
    """
    self._current_story_run = result['run']
    try:
      for fail in result['fail']:
        self.Fail(fail)
      if result['histogram_dicts']:
        self.ImportHistogramDicts(result['histogram_dicts'])
      for scalar in result['scalars']:
        self.AddValue(scalar)
    finally:
      self._current_story_run = None

  def InterruptBenchmark(self, reason):
    """Mark the benchmark as interrupted.

    Interrupted benchmarks are assumed to be stuck in some irrecoverably
    broken state.

    Note that the interruption_reason will always be the first interruption.
    This is because later interruptions may be simply additional fallout from
    the first interruption.
    """
    assert reason, 'A reason string to interrupt must be provided.'
    logging.fatal(reason)
    self._interruption = self._interruption or reason

  def AddHistogram(self, hist):
    if self._ShouldAddHistogram(hist):
      diags = self._GetDiagnostics()
      for diag in diags.itervalues():
        self._histograms.AddSharedDiagnostic(diag)
      self._histograms.AddHistogram(hist, diags)

  def _GetDiagnostics(self):
    """Get benchmark and current story details as histogram diagnostics."""
    diag_values = [
        (reserved_infos.BENCHMARKS, self.benchmark_name),
        (reserved_infos.BENCHMARK_START, self.benchmark_start_us),
        (reserved_infos.BENCHMARK_DESCRIPTIONS, self.benchmark_description),
        (reserved_infos.LABELS, self.label),
        (reserved_infos.HAD_FAILURES, self.current_story_run.failed),
        (reserved_infos.STORIES, self.current_story.name),
        (reserved_infos.STORY_TAGS, self.current_story.GetStoryTagsList()),
        (reserved_infos.STORYSET_REPEATS, self.current_story_run.index),
        (reserved_infos.TRACE_START, self.current_story_run.start_us),
    ]

    diags = {}
    for diag, value in diag_values:
      if value is None or value == []:
        continue
      if diag.type == 'GenericSet' and not isinstance(value, list):
        value = [value]
      elif diag.type == 'DateRange':
        # We store timestamps in microseconds, DateRange expects milliseconds.
        value = value / 1e3  # pylint: disable=redefined-variable-type
      diag_class = all_diagnostics.GetDiagnosticClassForName(diag.type)
      diags[diag.name] = diag_class(value)
    return diags

  def ImportHistogramDicts(self, histogram_dicts, import_immediately=True):
    histograms = histogram_set.HistogramSet()
    histograms.ImportDicts(histogram_dicts)
    histograms.FilterHistograms(lambda hist: not self._ShouldAddHistogram(hist))
    dicts_to_add = histograms.AsDicts()

    # For measurements that add both TBMv2 and legacy metrics to results, we
    # want TBMv2 histograms be imported at the end, when PopulateHistogramSet is
    # called so that legacy histograms can be built, too, from scalar value
    # data.
    #
    # Measurements that add only TBMv2 metrics and also add scalar value data
    # should set import_immediately to True (i.e. the default behaviour) to
    # prevent PopulateHistogramSet from trying to build more histograms from the
    # scalar value data.
    if import_immediately:
      self._histograms.ImportDicts(dicts_to_add)
    else:
      self._histogram_dicts_to_add.extend(dicts_to_add)

  def _ShouldAddHistogram(self, hist):
    assert self._current_story_run, 'Not currently running test.'
    is_first_result = (
        self._current_story_run.story not in self._all_stories)
    # TODO(eakuefner): Stop doing this once AddValue doesn't exist
    stat_names = [
        '%s_%s' % (hist.name, s) for  s in hist.statistics_scalars.iterkeys()]
    return any(self._should_add_value(s, is_first_result) for s in stat_names)

  def AddValue(self, value):
    """Associate a legacy Telemetry value with the current story run.

    This should not be used in new benchmarks. All values/measurements should
    be recorded in traces.
    """
    assert self._current_story_run, 'Not currently running a story.'
    assert self._benchmark_enabled, 'Cannot add value to disabled results'

    self._ValidateValue(value)
    is_first_result = (
        self._current_story_run.story not in self._all_stories)

    if not self._should_add_value(value.name, is_first_result):
      return
    self._current_story_run.AddValue(value)

  def AddSharedDiagnosticToAllHistograms(self, name, diagnostic):
    self._histograms.AddSharedDiagnosticToAllHistograms(name, diagnostic)

  def Fail(self, failure):
    """Mark the current story run as failed.

    This method will print a GTest-style failure annotation and mark the
    current story run as failed.

    Args:
      failure: A string or exc_info describing the reason for failure.
    """
    # TODO(#4258): Relax this assertion.
    assert self._current_story_run, 'Not currently running test.'
    if isinstance(failure, basestring):
      failure_str = 'Failure recorded for page %s: %s' % (
          self._current_story_run.story.name, failure)
    else:
      failure_str = ''.join(traceback.format_exception(*failure))
    logging.error(failure_str)
    self._current_story_run.SetFailed(failure_str)

  def Skip(self, reason, is_expected=True):
    assert self._current_story_run, 'Not currently running test.'
    self._current_story_run.Skip(reason, is_expected)

  def CreateArtifact(self, name):
    assert self._current_story_run, 'Not currently running test.'
    return self._current_story_run.CreateArtifact(name)

  def CaptureArtifact(self, name):
    assert self._current_story_run, 'Not currently running test.'
    return self._current_story_run.CaptureArtifact(name)

  def AddTraces(self, traces, tbm_metrics=None):
    """Associate some recorded traces with the current story run.

    Args:
      traces: A TraceDataBuilder object with traces recorded from all
        tracing agents.
      tbm_metrics: Optional list of TBMv2 metrics to be computed from the
        input traces.
    """
    assert self._current_story_run, 'Not currently running test.'
    for part, filename in traces.IterTraceParts():
      artifact_name = posixpath.join('trace', part, os.path.basename(filename))
      with self.CaptureArtifact(artifact_name) as artifact_path:
        shutil.copy(filename, artifact_path)
    if tbm_metrics:
      self._current_story_run.SetTbmMetrics(tbm_metrics)

  def AddSummaryValue(self, value):
    assert value.page is None
    self._ValidateValue(value)
    self._all_summary_values.append(value)

  def _ValidateValue(self, value):
    assert isinstance(value, value_module.Value)
    if value.name not in self._representative_value_for_each_value_name:
      self._representative_value_for_each_value_name[value.name] = value
    representative_value = self._representative_value_for_each_value_name[
        value.name]
    assert value.IsMergableWith(representative_value)

  def PrintSummary(self):
    if self._benchmark_enabled:
      self._progress_reporter.DidFinishAllTests(self)

      # Only serialize the trace if output_format is json or html.
      if (self._output_dir and
          any(isinstance(o, html_output_formatter.HtmlOutputFormatter)
              for o in self._output_formatters)):
        # Just to make sure that html trace is there in artifacts dir
        results_processor.SerializeAndUploadHtmlTraces(self)

      for output_formatter in self._output_formatters:
        output_formatter.Format(self)
        output_formatter.PrintViewResults()
    else:
      for output_formatter in self._output_formatters:
        output_formatter.FormatDisabled(self)

  def FindAllPageSpecificValuesNamed(self, value_name):
    """DEPRECATED: New benchmarks should not use legacy values."""
    return [v for v in self.IterAllLegacyValues() if v.name == value_name]

  def IterRunsWithTraces(self):
    for run in self._IterAllStoryRuns():
      if run.HasArtifactsInDir('trace/'):
        yield run
