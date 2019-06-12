# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import datetime
import json
import logging
import os
import random
import tempfile
import time
import traceback

import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

from telemetry import value as value_module
from telemetry.internal.results import chart_json_output_formatter
from telemetry.internal.results import html_output_formatter
from telemetry.internal.results import progress_reporter as reporter_module
from telemetry.internal.results import story_run
from telemetry.value import common_value_helpers
from telemetry.value import trace

from tracing.metrics import metric_runner
from tracing.value import convert_chart_json
from tracing.value import histogram_set
from tracing.value.diagnostics import all_diagnostics
from tracing.value.diagnostics import reserved_infos

_TEN_MINUTES = 60*10


def _ComputeMetricsInPool((run, trace_value)):
  story_name = run.story.name
  try:
    assert not trace_value.is_serialized, (
        "%s: TraceValue should not be serialized." % story_name)
    retvalue = {
        'run': run,
        'fail': [],
        'histogram_dicts': None,
        'scalars': []
    }
    extra_import_options = {
        'trackDetailedModelStats': True
    }

    logging.info('%s: Serializing trace.', story_name)
    trace_value.SerializeTraceData()
    trace_size_in_mib = os.path.getsize(trace_value.filename) / (2 ** 20)
    # Bails out on trace that are too big. See crbug.com/812631 for more
    # details.
    if trace_size_in_mib > 400:
      retvalue['fail'].append(
          '%s: Trace size is too big: %s MiB' % (story_name, trace_size_in_mib))
      return retvalue

    logging.info('%s: Starting to compute metrics on trace.', story_name)
    start = time.time()
    # This timeout needs to be coordinated with the Swarming IO timeout for the
    # task that runs this code. If this timeout is longer or close in length
    # to the swarming IO timeout then we risk being forcibly killed for not
    # producing any output. Note that this could be fixed by periodically
    # outputing logs while waiting for metrics to be calculated.
    timeout = _TEN_MINUTES
    mre_result = metric_runner.RunMetricOnSingleTrace(
        trace_value.filename, trace_value.timeline_based_metric,
        extra_import_options, canonical_url=trace_value.trace_url,
        timeout=timeout)
    logging.info('%s: Computing metrics took %.3f seconds.' % (
        story_name, time.time() - start))

    if mre_result.failures:
      for f in mre_result.failures:
        retvalue['fail'].append('%s: %s' % (story_name, str(f)))

    histogram_dicts = mre_result.pairs.get('histograms', [])
    retvalue['histogram_dicts'] = histogram_dicts

    scalars = []
    for d in mre_result.pairs.get('scalars', []):
      scalars.append(common_value_helpers.TranslateScalarValue(
          d, trace_value.page))
    retvalue['scalars'] = scalars
    return retvalue
  except Exception as e:  # pylint: disable=broad-except
    # logging exception here is the only way to get a stack trace since
    # multiprocessing's pool implementation does not save that data. See
    # crbug.com/953365.
    logging.error('%s: Exception while calculating metric', story_name)
    logging.exception(e)
    raise


class TelemetryInfo(object):
  def __init__(self, upload_bucket=None, output_dir=None):
    self._benchmark_name = None
    self._benchmark_start_us = None
    self._benchmark_interrupted = False
    self._benchmark_descriptions = None
    self._label = None
    self._story_name = ''
    self._story_tags = set()
    self._story_grouping_keys = {}
    self._storyset_repeat_counter = 0
    self._trace_start_us = None
    self._upload_bucket = upload_bucket
    self._trace_remote_path = None
    self._output_dir = output_dir
    self._trace_local_path = None
    self._had_failures = None
    self._diagnostics = {}

  @property
  def upload_bucket(self):
    return self._upload_bucket

  @property
  def benchmark_name(self):
    return self._benchmark_name

  @benchmark_name.setter
  def benchmark_name(self, benchmark_name):
    assert self.benchmark_name is None, (
        'benchmark_name must be set exactly once')
    self._benchmark_name = benchmark_name

  @property
  def benchmark_start_epoch(self):
    """ This field is DEPRECATED. Please use benchmark_start_us instead.
    """
    return self._benchmark_start_us / 1e6

  @benchmark_start_epoch.setter
  def benchmark_start_epoch(self, benchmark_start_epoch):
    """ This field is DEPRECATED. Please use benchmark_start_us instead.
    """
    assert self._benchmark_start_us is None, (
        'benchmark_start must be set exactly once')
    self._benchmark_start_us = benchmark_start_epoch * 1e6

  @property
  def benchmark_start_us(self):
    return self._benchmark_start_us

  @benchmark_start_us.setter
  def benchmark_start_us(self, benchmark_start_us):
    assert self._benchmark_start_us is None, (
        'benchmark_start must be set exactly once')
    self._benchmark_start_us = benchmark_start_us

  @property
  def benchmark_descriptions(self):
    return self._benchmark_descriptions

  @benchmark_descriptions.setter
  def benchmark_descriptions(self, benchmark_descriptions):
    assert self._benchmark_descriptions is None, (
        'benchmark_descriptions must be set exactly once')
    self._benchmark_descriptions = benchmark_descriptions

  @property
  def trace_start_us(self):
    return self._trace_start_us

  @property
  def benchmark_interrupted(self):
    return self._benchmark_interrupted

  @property
  def label(self):
    return self._label

  @label.setter
  def label(self, label):
    assert self.label is None, 'label cannot be set more than once'
    self._label = label

  @property
  def story_display_name(self):
    return self._story_name

  @property
  def story_grouping_keys(self):
    return self._story_grouping_keys

  @property
  def story_tags(self):
    return self._story_tags

  @property
  def storyset_repeat_counter(self):
    return self._storyset_repeat_counter

  @property
  def had_failures(self):
    return self._had_failures

  @property
  def diagnostics(self):
    return self._diagnostics

  @had_failures.setter
  def had_failures(self, had_failures):
    assert self.had_failures is None, (
        'had_failures cannot be set more than once')
    self._had_failures = had_failures

  def GetStoryTagsList(self):
    return list(self._story_tags) + [
        '%s:%s' % kv for kv in self._story_grouping_keys.iteritems()]

  def InterruptBenchmark(self):
    self._benchmark_interrupted = True

  def WillRunStory(self, story, storyset_repeat_counter):
    self._trace_start_us = time.time() * 1e6
    self._story_name = story.name
    self._story_grouping_keys = story.grouping_keys
    self._story_tags = story.tags
    self._storyset_repeat_counter = storyset_repeat_counter

    trace_name_suffix = '%s_%s.html' % (
        datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
        random.randint(1, 1e5))
    if self.label:
      trace_name = '%s_%s_%s' % (
          story.file_safe_name, self.label, trace_name_suffix)
    else:
      trace_name = '%s_%s' % (
          story.file_safe_name, trace_name_suffix)

    if self._upload_bucket:
      self._trace_remote_path = trace_name

    if self._output_dir:
      self._trace_local_path = os.path.abspath(os.path.join(
          self._output_dir, trace_name))

    self._UpdateDiagnostics()

  @property
  def trace_local_path(self):
    return self._trace_local_path

  @property
  def trace_local_url(self):
    if self._trace_local_path:
      return 'file://' + self._trace_local_path
    return None

  @property
  def trace_remote_path(self):
    return self._trace_remote_path

  @property
  def trace_remote_url(self):
    if self._trace_remote_path:
      return 'https://console.developers.google.com/m/cloudstorage/b/%s/o/%s' % (
          self._upload_bucket, self._trace_remote_path)
    return None

  @property
  def trace_url(self):
    # This is MRE's canonicalUrl.
    if self._upload_bucket is None:
      return self.trace_local_url
    return self.trace_remote_url

  def _UpdateDiagnostics(self):
    """ Benchmarks that add histograms but don't use
    timeline_base_measurement need to add shared diagnostics separately.
    Make them available on the telemetry info."""
    def SetDiagnosticsValue(info, value):
      if value is None or value == []:
        return

      if info.type == 'GenericSet' and not isinstance(value, list):
        value = [value]
      elif info.type == 'DateRange':
        # We store timestamps in microseconds, DateRange expects milliseconds.
        value = value / 1e3
      diag_class = all_diagnostics.GetDiagnosticClassForName(info.type)
      self.diagnostics[info.name] = diag_class(value)

    SetDiagnosticsValue(reserved_infos.BENCHMARKS, self.benchmark_name)
    SetDiagnosticsValue(reserved_infos.BENCHMARK_START, self.benchmark_start_us)
    SetDiagnosticsValue(reserved_infos.BENCHMARK_DESCRIPTIONS,
                        self.benchmark_descriptions)
    SetDiagnosticsValue(reserved_infos.LABELS, self.label)
    SetDiagnosticsValue(reserved_infos.HAD_FAILURES, self.had_failures)
    SetDiagnosticsValue(reserved_infos.STORIES, self._story_name)
    SetDiagnosticsValue(reserved_infos.STORY_TAGS, self.GetStoryTagsList())
    SetDiagnosticsValue(reserved_infos.STORYSET_REPEATS,
                        self.storyset_repeat_counter)
    SetDiagnosticsValue(reserved_infos.TRACE_START, self.trace_start_us)
    SetDiagnosticsValue(reserved_infos.TRACE_URLS, self.trace_url)


class PageTestResults(object):
  def __init__(self, output_formatters=None,
               progress_reporter=None, output_dir=None,
               should_add_value=None,
               benchmark_enabled=True, upload_bucket=None,
               benchmark_metadata=None):
    """
    Args:
      output_formatters: A list of output formatters. The output
          formatters are typically used to format the test results, such
          as CsvPivotTableOutputFormatter, which output the test results as CSV.
      progress_reporter: An instance of progress_reporter.ProgressReporter,
          to be used to output test status/results progressively.
      output_dir: A string specified the directory where to store the test
          artifacts, e.g: trace, videos,...
      should_add_value: A function that takes two arguments: a value name and
          a boolean (True when the value belongs to the first run of the
          corresponding story). It returns True if the value should be added
          to the test results and False otherwise.
      benchmark_metadata: A benchmark.BenchmarkMetadata object. This is used in
          the chart JSON output formatter.
    """
    super(PageTestResults, self).__init__()
    self._progress_reporter = (
        progress_reporter if progress_reporter is not None
        else reporter_module.ProgressReporter())
    self._output_formatters = (
        output_formatters if output_formatters is not None else [])
    self._output_dir = output_dir
    if should_add_value is not None:
      self._should_add_value = should_add_value
    else:
      self._should_add_value = lambda v, is_first: True

    self._current_page_run = None
    self._all_page_runs = []
    self._all_stories = set()
    self._representative_value_for_each_value_name = {}
    self._all_summary_values = []
    self._serialized_trace_file_ids_to_paths = {}

    self._histograms = histogram_set.HistogramSet()

    self._telemetry_info = TelemetryInfo(
        upload_bucket=upload_bucket, output_dir=output_dir)

    # State of the benchmark this set of results represents.
    self._benchmark_enabled = benchmark_enabled

    self._benchmark_metadata = benchmark_metadata

    self._histogram_dicts_to_add = []

    # Mapping of the stories that have run to the number of times they have run
    # This is necessary on interrupt if some of the stories did not run.
    self._story_run_count = {}

  @property
  def telemetry_info(self):
    return self._telemetry_info

  def AsHistogramDicts(self):
    return self._histograms.AsDicts()

  def PopulateHistogramSet(self):
    if len(self._histograms):
      return

    chart_json = chart_json_output_formatter.ResultsAsChartDict(
        self._benchmark_metadata, self)
    info = self.telemetry_info
    chart_json['label'] = info.label
    chart_json['benchmarkStartMs'] = info.benchmark_start_us / 1000.0

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

  def __copy__(self):
    cls = self.__class__
    result = cls.__new__(cls)
    for k, v in self.__dict__.items():
      if isinstance(v, collections.Container):
        v = copy.copy(v)
      setattr(result, k, v)
    return result

  @property
  def serialized_trace_file_ids_to_paths(self):
    return self._serialized_trace_file_ids_to_paths

  @property
  def all_page_specific_values(self):
    values = []
    for run in self._IterAllStoryRuns():
      values += run.values
    return values

  @property
  def all_summary_values(self):
    return self._all_summary_values

  @property
  def current_page(self):
    assert self._current_page_run, 'Not currently running test.'
    return self._current_page_run.story

  @property
  def current_page_run(self):
    assert self._current_page_run, 'Not currently running test.'
    return self._current_page_run

  @property
  def all_page_runs(self):
    return self._all_page_runs

  @property
  def pages_that_succeeded(self):
    """Returns the set of pages that succeeded.

    Note: This also includes skipped pages.
    """
    pages = set(run.story for run in self.all_page_runs)
    pages.difference_update(self.pages_that_failed)
    return pages

  @property
  def pages_that_succeeded_and_not_skipped(self):
    """Returns the set of pages that succeeded and werent skipped."""
    skipped_story_names = set(
        run.story.name for run in self._IterAllStoryRuns() if run.skipped)
    pages = self.pages_that_succeeded
    for page in self.pages_that_succeeded:
      if page.name in skipped_story_names:
        pages.remove(page)
    return pages

  @property
  def pages_that_failed(self):
    """Returns the set of failed pages."""
    failed_pages = set()
    for run in self.all_page_runs:
      if run.failed:
        failed_pages.add(run.story)
    return failed_pages

  @property
  def had_successes_not_skipped(self):
    return bool(self.pages_that_succeeded_and_not_skipped)

  @property
  def had_failures(self):
    return any(run.failed for run in self.all_page_runs)

  @property
  def num_failed(self):
    return sum(1 for run in self.all_page_runs if run.failed)

  # TODO(#4229): Remove this once tools/perf is migrated.
  @property
  def failures(self):
    return [None] * self.num_failed

  @property
  def had_skips(self):
    return any(run.skipped for run in self._IterAllStoryRuns())

  def _IterAllStoryRuns(self):
    for run in self._all_page_runs:
      yield run
    if self._current_page_run:
      yield self._current_page_run

  def _GetStringFromExcInfo(self, err):
    return ''.join(traceback.format_exception(*err))

  def CleanUp(self):
    """Clean up any TraceValues contained within this results object."""
    for run in self._all_page_runs:
      for v in run.values:
        if isinstance(v, trace.TraceValue):
          v.CleanUp()
          run.values.remove(v)

  def CloseOutputFormatters(self):
    """
    Clean up any open output formatters contained within this results object
    """
    for output_formatter in self._output_formatters:
      output_formatter.output_stream.close()

  def __enter__(self):
    return self

  def __exit__(self, _, __, ___):
    self.CleanUp()
    self.CloseOutputFormatters()

  def WillRunPage(self, page, storyset_repeat_counter=0):
    assert not self._current_page_run, 'Did not call DidRunPage.'
    self._current_page_run = story_run.StoryRun(page, self._output_dir)
    self._progress_reporter.WillRunPage(self)
    self.telemetry_info.WillRunStory(
        page, storyset_repeat_counter)

  def DidRunPage(self, page):  # pylint: disable=unused-argument
    """
    Args:
      page: The current page under test.
    """
    assert self._current_page_run, 'Did not call WillRunPage.'
    self._current_page_run.Finish()
    self._progress_reporter.DidRunPage(self)
    self._all_page_runs.append(self._current_page_run)
    story = self._current_page_run.story
    self._all_stories.add(story)
    if bool(self._story_run_count.get(story)):
      self._story_run_count[story] += 1
    else:
      self._story_run_count[story] = 1
    self._current_page_run = None

  def _AddPageResults(self, result):
    self._current_page_run = result['run']
    try:
      for fail in result['fail']:
        self.Fail(fail)
      if result['histogram_dicts']:
        self.ImportHistogramDicts(result['histogram_dicts'])
      for scalar in result['scalars']:
        self.AddValue(scalar)
    finally:
      self._current_page_run = None

  def ComputeTimelineBasedMetrics(self):
    assert not self._current_page_run, 'Cannot compute metrics while running.'
    def _GetCpuCount():
      try:
        return multiprocessing.cpu_count()
      except NotImplementedError:
        # Some platforms can raise a NotImplementedError from cpu_count()
        logging.warn('cpu_count() not implemented.')
        return 8

    runs_and_values = self._FindRunsAndValuesWithTimelineBasedMetrics()
    if not runs_and_values:
      return

    # Note that this is speculatively halved as an attempt to fix
    # crbug.com/953365.
    threads_count = min(_GetCpuCount()/2 or 1, len(runs_and_values))
    pool = ThreadPool(threads_count)
    try:
      for result in pool.imap_unordered(_ComputeMetricsInPool,
                                        runs_and_values):
        self._AddPageResults(result)
    finally:
      pool.terminate()
      pool.join()

  def InterruptBenchmark(self, stories, repeat_count):
    self.telemetry_info.InterruptBenchmark()
    # If we are in the middle of running a page it didn't finish
    # so reset the current page run
    self._current_page_run = None
    for story in stories:
      num_runs = repeat_count - self._story_run_count.get(story, 0)
      for i in xrange(num_runs):
        self._GenerateSkippedStoryRun(story, i)

  def _GenerateSkippedStoryRun(self, story, storyset_repeat_counter):
    self.WillRunPage(story, storyset_repeat_counter)
    self.Skip('Telemetry interrupted', is_expected=False)
    self.DidRunPage(story)

  def AddHistogram(self, hist):
    if self._ShouldAddHistogram(hist):
      diags = self._telemetry_info.diagnostics
      for _, diag in diags.items():
        self._histograms.AddSharedDiagnostic(diag)
      self._histograms.AddHistogram(hist, diags)

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
    assert self._current_page_run, 'Not currently running test.'
    is_first_result = (
        self._current_page_run.story not in self._all_stories)
    # TODO(eakuefner): Stop doing this once AddValue doesn't exist
    stat_names = [
        '%s_%s' % (hist.name, s) for  s in hist.statistics_scalars.iterkeys()]
    return any(self._should_add_value(s, is_first_result) for s in stat_names)

  def AddValue(self, value):
    assert self._current_page_run, 'Not currently running test.'
    assert self._benchmark_enabled, 'Cannot add value to disabled results'

    self._ValidateValue(value)
    is_first_result = (
        self._current_page_run.story not in self._all_stories)

    story_keys = self._current_page_run.story.grouping_keys

    if story_keys:
      for k, v in story_keys.iteritems():
        assert k not in value.grouping_keys, (
            'Tried to add story grouping key ' + k + ' already defined by ' +
            'value')
        value.grouping_keys[k] = v

      # We sort by key name to make building the tir_label deterministic.
      story_keys_label = '_'.join(v for _, v in sorted(story_keys.iteritems()))
      if value.tir_label:
        assert value.tir_label == story_keys_label, (
            'Value has an explicit tir_label (%s) that does not match the '
            'one computed from story_keys (%s)' % (value.tir_label, story_keys))
      else:
        value.tir_label = story_keys_label

    if not (isinstance(value, trace.TraceValue) or
            self._should_add_value(value.name, is_first_result)):
      return
    self._current_page_run.AddValue(value)

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
    assert self._current_page_run, 'Not currently running test.'
    if isinstance(failure, basestring):
      failure_str = 'Failure recorded for page %s: %s' % (
          self._current_page_run.story.name, failure)
    else:
      failure_str = ''.join(traceback.format_exception(*failure))
    logging.error(failure_str)
    self._current_page_run.SetFailed(failure_str)

  def Skip(self, reason, is_expected=True):
    assert self._current_page_run, 'Not currently running test.'
    self._current_page_run.Skip(reason, is_expected)

  def CreateArtifact(self, name, prefix='', suffix=''):
    assert self._current_page_run, 'Not currently running test.'
    return self._current_page_run.CreateArtifact(name, prefix, suffix)

  def AddArtifact(self, name, path):
    assert self._current_page_run, 'Not currently running test.'
    self._current_page_run.AddArtifact(name, path)

  def AddTraces(self, traces, tbm_metrics=None):
    """Associate some recorded traces with the current story run.

    Args:
      traces: A TraceDataBuilder object with traces recorded from all
        tracing agents.
      tbm_metrics: Optional list of TBMv2 metrics to be computed from the
        input traces.
    """
    assert self._current_page_run, 'Not currently running test.'
    trace_value = trace.TraceValue(
        self.current_page, traces,
        file_path=self.telemetry_info.trace_local_path,
        remote_path=self.telemetry_info.trace_remote_path,
        upload_bucket=self.telemetry_info.upload_bucket,
        cloud_url=self.telemetry_info.trace_remote_url,
        trace_url=self.telemetry_info.trace_url)
    self.AddValue(trace_value)
    if tbm_metrics:
      # Both trace serialization and metric computation will happen later
      # asynchronously during ComputeTimelineBasedMetrics.
      trace_value.SetTimelineBasedMetrics(tbm_metrics)
    else:
      # Otherwise we immediately serialize the trace data.
      trace_value.SerializeTraceData()

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
        self._SerializeTracesToDirPath()

      for output_formatter in self._output_formatters:
        output_formatter.Format(self)
        output_formatter.PrintViewResults()
    else:
      for output_formatter in self._output_formatters:
        output_formatter.FormatDisabled(self)

  def FindValues(self, predicate):
    """Finds all values matching the specified predicate.

    Args:
      predicate: A function that takes a Value and returns a bool.
    Returns:
      A list of values matching |predicate|.
    """
    values = []
    for value in self.all_page_specific_values:
      if predicate(value):
        values.append(value)
    return values

  def FindPageSpecificValuesForPage(self, page, value_name):
    return self.FindValues(lambda v: v.page == page and v.name == value_name)

  def FindAllPageSpecificValuesNamed(self, value_name):
    return self.FindValues(lambda v: v.name == value_name)

  def FindAllPageSpecificValuesFromIRNamed(self, tir_label, value_name):
    return self.FindValues(lambda v: v.name == value_name
                           and v.tir_label == tir_label)

  def FindAllTraceValues(self):
    return self.FindValues(lambda v: isinstance(v, trace.TraceValue))

  def _FindRunsAndValuesWithTimelineBasedMetrics(self):
    values = []
    for run in self._all_page_runs:
      for v in run.values:
        if isinstance(v, trace.TraceValue) and v.timeline_based_metric:
          values.append((run, v))
    return values

  def _SerializeTracesToDirPath(self):
    """ Serialize all trace values to files in dir_path and return a list of
    file handles to those files. """
    for value in self.FindAllTraceValues():
      fh = value.Serialize()
      self._serialized_trace_file_ids_to_paths[fh.id] = fh.GetAbsPath()

  def UploadTraceFilesToCloud(self):
    for value in self.FindAllTraceValues():
      value.UploadToCloud()

  #TODO(crbug.com/772216): Remove this once the uploading is done by Chromium
  # test recipe.
  def UploadArtifactsToCloud(self):
    bucket = self.telemetry_info.upload_bucket
    for run in self._all_page_runs:
      run.UploadArtifactsToCloud(bucket)
