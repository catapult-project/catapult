# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

import json

from google.appengine.api import taskqueue

from dashboard import post_data_handler
from dashboard.common import datastore_hooks
from tracing.value import histogram as histogram_module


SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.BuildbotInfo, histogram_module.DeviceInfo])
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
  histograms = histogram_module.HistogramSet()
  histograms.ImportDicts(histogram_dicts)
  histograms.ResolveRelatedHistograms()
  InlineDenseSharedDiagnostics(histograms)

  test_path = ComputeTestPath(histograms)
  revision = ComputeRevision(histograms)

  task_list = []
  for d in histograms.AsDicts():
    task_list.append(taskqueue.Task(
        url='/add_histograms_queue', params={
            'data': json.dumps(d),
            'test_path': test_path,
            'revision': revision}))

  queue = taskqueue.Queue(TASK_QUEUE_NAME)
  queue.add(task_list)


def ComputeTestPath(histograms):
  # TODO(eakuefner): Make this implementation less bogus
  del histograms
  return 'TestMaster/TestBot/TestSuite/TestMetric'


def ComputeRevision(histograms):
  # TODO(eakuefner): Make this implementation less bogus
  del histograms
  return 123456


def InlineDenseSharedDiagnostics(histograms):
  # TODO(eakuefner): Delete inlined diagnostics from the set
  for histogram in histograms:
    diagnostics = histogram.diagnostics
    for diagnostic in diagnostics.itervalues():
      if type(diagnostic) not in SPARSE_DIAGNOSTIC_TYPES:
        diagnostic.Inline()
