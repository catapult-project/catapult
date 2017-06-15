# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

import json

from google.appengine.api import taskqueue

from dashboard import post_data_handler
from dashboard.common import datastore_hooks
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set


SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.BuildbotInfo, histogram_module.DeviceInfo,
     histogram_module.Ownership])
HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.TelemetryInfo])
SPARSE_DIAGNOSTIC_TYPES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES)


TASK_QUEUE_NAME = 'histograms-queue'


class BadRequestError(Exception):
  pass


class AddHistogramsHandler(post_data_handler.PostDataHandler):

  def post(self):
    datastore_hooks.SetPrivilegedRequest()

    data_str = self.request.get('data')
    if not data_str:
      self.ReportError('Missing "data" parameter', status=400)
      return

    try:
      histogram_dicts = json.loads(data_str)
      ProcessHistogramSet(histogram_dicts)
    except ValueError:
      self.ReportError('Invalid JSON string', status=400)
    except BadRequestError as e:
      self.ReportError(e.message, status=400)


def ProcessHistogramSet(histogram_dicts):
  if not isinstance(histogram_dicts, list):
    raise BadRequestError('HistogramSet JSON much be a list of dicts')
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(histogram_dicts)
  histograms.ResolveRelatedHistograms()
  InlineDenseSharedDiagnostics(histograms)

  revision = ComputeRevision(histograms)

  task_list = []

  suite_path = ComputeSuitePath(histograms)

  for diagnostic in histograms.shared_diagnostics:
    # We'll skip the histogram-level sparse diagnostics because we need to
    # handle those with the histograms, below, so that we can properly assign
    # test paths.
    if type(diagnostic) in SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES:
      task_list.append(_MakeTask(diagnostic, suite_path, revision))

  for histogram in histograms:
    guid = histogram.guid
    objects = FindHistogramLevelSparseDiagnostics(guid, histograms)
    test_path = ComputeTestPath(guid, histograms)
    # We need to queue the histogram in addition to its dense shared
    # diagnostics.
    objects.append(histogram)
    # TODO(eakuefner): Batch these better than one per task.
    for obj in objects:
      task_list.append(_MakeTask(obj, test_path, revision))

  queue = taskqueue.Queue(TASK_QUEUE_NAME)
  queue.add(task_list)


def _MakeTask(obj, test_path, revision):
  return taskqueue.Task(
      url='/add_histograms_queue', params={
          'data': json.dumps(obj.AsDict()),
          'test_path': test_path,
          'revision': revision})


def FindHistogramLevelSparseDiagnostics(guid, histograms):
  histogram = histograms.LookupHistogram(guid)
  diagnostics = []
  for diagnostic in histogram.diagnostics.itervalues():
    if type(diagnostic) in HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES:
      diagnostics.append(diagnostic)
  return diagnostics


def ComputeSuitePath(histograms):
  assert len(histograms) > 0
  return _ComputeSuitePathFromHistogram(histograms.GetFirstHistogram())


def ComputeTestPath(guid, histograms):
  histogram = histograms.LookupHistogram(guid)
  suite_path = _ComputeSuitePathFromHistogram(histogram)
  telemetry_info = histogram.diagnostics[histogram_module.TelemetryInfo.NAME]
  story_display_name = telemetry_info.story_display_name

  path = '%s/%s' % (suite_path, histogram.name)

  if story_display_name != '':
    path += '/%s' % story_display_name

  return path


def _ComputeSuitePathFromHistogram(histogram):
  buildbot_info = histogram.diagnostics[histogram_module.BuildbotInfo.NAME]
  telemetry_info = histogram.diagnostics[histogram_module.TelemetryInfo.NAME]

  master = buildbot_info.display_master_name
  bot = buildbot_info.display_bot_name
  benchmark = telemetry_info.benchmark_name

  return '%s/%s/%s' % (master, bot, benchmark)


def ComputeRevision(histograms):
  assert len(histograms) > 0
  revision_info = histograms.GetFirstHistogram().diagnostics[
      histogram_module.RevisionInfo.NAME]
  return revision_info.chromium_commit_position


def InlineDenseSharedDiagnostics(histograms):
  # TODO(eakuefner): Delete inlined diagnostics from the set
  for histogram in histograms:
    diagnostics = histogram.diagnostics
    for diagnostic in diagnostics.itervalues():
      if type(diagnostic) not in SPARSE_DIAGNOSTIC_TYPES:
        diagnostic.Inline()
