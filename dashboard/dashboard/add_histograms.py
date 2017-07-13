# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

import json
import sys

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import add_point_queue
from dashboard.api import api_request_handler
from dashboard.common import datastore_hooks
from dashboard.common import stored_object
from dashboard.models import histogram
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic


SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.BuildbotInfo, histogram_module.DeviceInfo,
     histogram_module.Ownership])
HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.TelemetryInfo])
SPARSE_DIAGNOSTIC_TYPES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES)


TASK_QUEUE_NAME = 'histograms-queue'


def _CheckRequest(condition, msg):
  if not condition:
    raise api_request_handler.BadRequestError(msg)


class AddHistogramsHandler(api_request_handler.ApiRequestHandler):

  def AuthorizedPost(self):
    datastore_hooks.SetPrivilegedRequest()

    data_str = self.request.get('data')
    if not data_str:
      raise api_request_handler.BadRequestError('Missing "data" parameter')

    histogram_dicts = json.loads(data_str)
    ProcessHistogramSet(histogram_dicts)


def ProcessHistogramSet(histogram_dicts):
  if not isinstance(histogram_dicts, list):
    raise api_request_handler.BadRequestError(
        'HistogramSet JSON much be a list of dicts')
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(histogram_dicts)
  histograms.ResolveRelatedHistograms()
  InlineDenseSharedDiagnostics(histograms)

  revision = ComputeRevision(histograms)

  task_list = []

  suite_key = GetSuiteKey(histograms)

  suite_level_sparse_diagnostic_entities = []
  for diag in histograms.shared_diagnostics:
    # We'll skip the histogram-level sparse diagnostics because we need to
    # handle those with the histograms, below, so that we can properly assign
    # test paths.
    if type(diag) in SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES:
      suite_level_sparse_diagnostic_entities.append(
          histogram.SparseDiagnostic(
              id=diag.guid, data=diag.AsDict(), test=suite_key,
              start_revision=revision, end_revision=sys.maxint))

  # TODO(eakuefner): Refactor master/bot computation to happen above this line
  # so that we can replace with a DiagnosticRef rather than a full diagnostic.
  new_guids_to_old_diagnostics = DeduplicateAndPut(
      suite_level_sparse_diagnostic_entities, suite_key, revision)
  for new_guid, old_diagnostic in new_guids_to_old_diagnostics.iteritems():
    histograms.ReplaceSharedDiagnostic(
        new_guid, diagnostic.Diagnostic.FromDict(old_diagnostic))

  for hist in histograms:
    guid = hist.guid
    diagnostics = FindHistogramLevelSparseDiagnostics(guid, histograms)
    # TODO(eakuefner): Don't compute full diagnostics, because we need anyway to
    # call GetOrCreate here and in the queue.
    test_path = ComputeTestPath(guid, histograms)
    # TODO(eakuefner): Batch these better than one per task.
    task_list.append(_MakeTask(hist, test_path, revision, diagnostics))

  queue = taskqueue.Queue(TASK_QUEUE_NAME)
  queue.add(task_list)


def _MakeTask(hist, test_path, revision, diagnostics=None):
  params = {
      'data': json.dumps(hist.AsDict()),
      'test_path': test_path,
      'revision': revision
  }
  if diagnostics is not None:
    params['diagnostics'] = json.dumps([d.AsDict() for d in diagnostics])
  return taskqueue.Task(url='/add_histograms_queue', params=params)


# TODO(eakuefner): Clean this up by making it accept raw diagnostics.
# TODO(eakuefner): Move this helper along with others to a common place.
def DeduplicateAndPut(new_entities, test, rev):
  query = histogram.SparseDiagnostic.query(
      ndb.AND(
          histogram.SparseDiagnostic.end_revision == sys.maxint,
          histogram.SparseDiagnostic.test == test))
  diagnostic_entities = query.fetch()
  entity_futures = []
  new_guids_to_existing_diagnostics = {}
  for new_entity in new_entities:
    type_str = new_entity.data['type']
    old_entity = _GetDiagnosticEntityMatchingType(type_str, diagnostic_entities)
    if old_entity is not None:
      # Case 1: One in datastore, different from new one.
      if _IsDifferent(old_entity.data, new_entity.data):
        old_entity.end_revision = rev - 1
        entity_futures.append(old_entity.put_async())
        new_entity.start_revision = rev
        new_entity.end_revision = sys.maxint
        entity_futures.append(new_entity.put_async())
      # Case 2: One in datastore, same as new one.
      else:
        new_guids_to_existing_diagnostics[new_entity.key.id()] = old_entity.data
      continue
    # Case 3: Nothing in datastore.
    entity_futures.append(new_entity.put_async())
  ndb.Future.wait_all(entity_futures)
  return new_guids_to_existing_diagnostics


def _GetDiagnosticEntityMatchingType(type_str, diagnostic_entities):
  for entity in diagnostic_entities:
    if entity.data['type'] == type_str:
      return entity


def _IsDifferent(diagnostic_a, diagnostic_b):
  return (diagnostic.Diagnostic.FromDict(diagnostic_a) !=
          diagnostic.Diagnostic.FromDict(diagnostic_b))


def FindHistogramLevelSparseDiagnostics(guid, histograms):
  hist = histograms.LookupHistogram(guid)
  diagnostics = []
  for diag in hist.diagnostics.itervalues():
    if type(diag) in HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES:
      diagnostics.append(diag)
  return diagnostics


def GetSuiteKey(histograms):
  assert len(histograms) > 0
  # TODO(eakuefner): Refactor this to coalesce the boilerplate (note that this
  # is all also being done in add_histograms_queue's post handler)
  master, bot, benchmark = _GetMasterBotBenchmarkFromHistogram(
      histograms.GetFirstHistogram())
  bot_whitelist = stored_object.Get(add_point_queue.BOT_WHITELIST_KEY)
  internal_only = add_point_queue.BotInternalOnly(bot, bot_whitelist)
  return add_point_queue.GetOrCreateAncestors(
      master, bot, benchmark, internal_only).key


def ComputeTestPath(guid, histograms):
  hist = histograms.LookupHistogram(guid)
  suite_path = '%s/%s/%s' % _GetMasterBotBenchmarkFromHistogram(hist)
  telemetry_info = hist.diagnostics[
      histogram_module.RESERVED_NAMES['TELEMETRY']]
  story_display_name = telemetry_info.story_display_name

  path = '%s/%s' % (suite_path, hist.name)

  if story_display_name != '':
    path += '/%s' % story_display_name

  return path


def _GetMasterBotBenchmarkFromHistogram(hist):
  _CheckRequest(histogram_module.RESERVED_NAMES['BUILDBOT'] in hist.diagnostics,
                'Histograms must have BuildbotInfo attached')
  buildbot_info = hist.diagnostics[histogram_module.RESERVED_NAMES['BUILDBOT']]
  _CheckRequest(
      histogram_module.RESERVED_NAMES['TELEMETRY'] in hist.diagnostics,
      'Histograms must have TelemetryInfo attached')
  telemetry_info = hist.diagnostics[
      histogram_module.RESERVED_NAMES['TELEMETRY']]

  master = buildbot_info.display_master_name
  bot = buildbot_info.display_bot_name
  benchmark = telemetry_info.benchmark_name

  return master, bot, benchmark


def ComputeRevision(histograms):
  _CheckRequest(len(histograms) > 0, 'Must upload at least one histogram')
  diagnostics = histograms.GetFirstHistogram().diagnostics
  _CheckRequest(histogram_module.RESERVED_NAMES['REVISIONS'] in diagnostics,
                'Histograms must have RevisionInfo attached')
  revision_info = diagnostics[histogram_module.RESERVED_NAMES['REVISIONS']]
  # TODO(eakuefner): Allow users to specify other types of revisions to be used
  # for computing revisions of dashboard points. See
  # https://github.com/catapult-project/catapult/issues/3623.
  return revision_info.chromium_commit_position


def InlineDenseSharedDiagnostics(histograms):
  # TODO(eakuefner): Delete inlined diagnostics from the set
  for hist in histograms:
    diagnostics = hist.diagnostics
    for diag in diagnostics.itervalues():
      if type(diag) not in SPARSE_DIAGNOSTIC_TYPES:
        diag.Inline()
