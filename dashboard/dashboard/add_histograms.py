# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

import json
import logging
import sys
import uuid

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import add_point
from dashboard import add_point_queue
from dashboard.api import api_request_handler
from dashboard.common import datastore_hooks
from dashboard.common import histogram_helpers
from dashboard.common import stored_object
from dashboard.models import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import reserved_infos

SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES = set([
    reserved_infos.ARCHITECTURES.name,
    reserved_infos.BENCHMARKS.name,
    reserved_infos.BOTS.name,
    reserved_infos.BUG_COMPONENTS.name,
    reserved_infos.GPUS.name,
    reserved_infos.MASTERS.name,
    reserved_infos.MEMORY_AMOUNTS.name,
    reserved_infos.OS_NAMES.name,
    reserved_infos.OS_VERSIONS.name,
    reserved_infos.OWNERS.name,
    reserved_infos.PRODUCT_VERSIONS.name,
    reserved_infos.TAG_MAP.name,
])

HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES = set([
    reserved_infos.DEVICE_IDS.name,
    reserved_infos.GPUS.name,
    reserved_infos.MEMORY_AMOUNTS.name,
    reserved_infos.PRODUCT_VERSIONS.name,
    reserved_infos.RELATED_NAMES.name,
    reserved_infos.STORIES.name,
    reserved_infos.STORYSET_REPEATS.name,
    reserved_infos.STORY_TAGS.name,
])

SPARSE_DIAGNOSTIC_NAMES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES)


TASK_QUEUE_NAME = 'histograms-queue'


def _CheckRequest(condition, msg):
  if not condition:
    raise api_request_handler.BadRequestError(msg)


class AddHistogramsHandler(api_request_handler.ApiRequestHandler):

  def AuthorizedPost(self):
    datastore_hooks.SetPrivilegedRequest()

    try:
      data_str = self.request.get('data')
      if not data_str:
        raise api_request_handler.BadRequestError('Missing "data" parameter')

      logging.info('Received data: %s', data_str)

      histogram_dicts = json.loads(data_str)
      ProcessHistogramSet(histogram_dicts)
    except api_request_handler.BadRequestError as e:
      # TODO(simonhatch, eakuefner: Remove this later.
      # When this has all stabilized a bit, remove and let this 400 to clients,
      # but for now to preven the waterfall from re-uploading over and over
      # while we bug fix, let's just log the error.
      # https://github.com/catapult-project/catapult/issues/4019
      logging.error(e.message)
    except Exception as e:  # pylint: disable=broad-except
      # TODO(simonhatch, eakuefner: Remove this later.
      # We shouldn't be catching ALL exceptions, this is just while the
      # stability of the endpoint is being worked on.
      logging.error(e.message)


def _LogDebugInfo(histograms):
  hist = histograms.GetFirstHistogram()
  if not hist:
    logging.info('No histograms in data.')
    return

  log_urls = hist.diagnostics.get(reserved_infos.LOG_URLS.name)
  if log_urls:
    log_urls = list(log_urls)
    logging.info('Buildbot URL: %s', str(log_urls))
  else:
    logging.info('No LOG_URLS in data.')


def ProcessHistogramSet(histogram_dicts):
  if not isinstance(histogram_dicts, list):
    raise api_request_handler.BadRequestError(
        'HistogramSet JSON much be a list of dicts')
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(histogram_dicts)
  histograms.ResolveRelatedHistograms()
  histograms.DeduplicateDiagnostics()

  _LogDebugInfo(histograms)

  InlineDenseSharedDiagnostics(histograms)
  revision = ComputeRevision(histograms)
  suite_key = GetSuiteKey(histograms)

  # We'll skip the histogram-level sparse diagnostics because we need to
  # handle those with the histograms, below, so that we can properly assign
  # test paths.
  suite_level_sparse_diagnostic_entities = FindSuiteLevelSparseDiagnostics(
      histograms, suite_key, revision)

  # TODO(eakuefner): Refactor master/bot computation to happen above this line
  # so that we can replace with a DiagnosticRef rather than a full diagnostic.
  new_guids_to_old_diagnostics = DeduplicateAndPut(
      suite_level_sparse_diagnostic_entities, suite_key, revision)
  for new_guid, old_diagnostic in new_guids_to_old_diagnostics.iteritems():
    histograms.ReplaceSharedDiagnostic(
        new_guid, diagnostic.Diagnostic.FromDict(old_diagnostic))

  task_list = []

  for hist in histograms:
    guid = hist.guid
    diagnostics = FindHistogramLevelSparseDiagnostics(guid, histograms)
    # TODO(eakuefner): Don't compute full diagnostics, because we need anyway to
    # call GetOrCreate here and in the queue.
    test_path = ComputeTestPath(guid, histograms)
    # TODO(eakuefner): Batch these better than one per task.
    task_list.append(_MakeTask(hist, test_path, revision, diagnostics))

  queue = taskqueue.Queue(TASK_QUEUE_NAME)

  futures = []
  for i in xrange(0, len(task_list), taskqueue.MAX_TASKS_PER_ADD):
    f = queue.add_async(task_list[i:i + taskqueue.MAX_TASKS_PER_ADD])
    futures.append(f)
  for f in futures:
    f.get_result()


def _MakeTask(hist, test_path, revision, diagnostics=None):
  params = {
      'data': json.dumps(hist.AsDict()),
      'test_path': test_path,
      'revision': revision
  }

  # By changing the GUID just before serializing the task, we're making it
  # unique for each histogram. This avoids each histogram trying to write the
  # same diagnostic out (datastore contention), at the cost of copyin the
  # data. These are sparsely written to datastore anyway, so the extra
  # storage should be minimal.
  diagnostics = {k: d.AsDict() for k, d in diagnostics.iteritems()}
  for d in diagnostics.itervalues():
    d['guid'] = str(uuid.uuid4())

  params['diagnostics'] = json.dumps(diagnostics)

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
    old_entity = _GetDiagnosticEntityMatchingName(
        new_entity.name, diagnostic_entities)
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


def _GetDiagnosticEntityMatchingName(name, diagnostic_entities):
  for entity in diagnostic_entities:
    if entity.name == name:
      return entity
  return None


def _IsDifferent(diagnostic_a, diagnostic_b):
  return (diagnostic.Diagnostic.FromDict(diagnostic_a) !=
          diagnostic.Diagnostic.FromDict(diagnostic_b))


def FindSuiteLevelSparseDiagnostics(histograms, suite_key, revision):
  diagnostics = {}
  for hist in histograms:
    for name, diag in hist.diagnostics.iteritems():
      if name in SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES:
        existing_entity = diagnostics.get(name)
        if existing_entity is None:
          diagnostics[name] = histogram.SparseDiagnostic(
              id=diag.guid, data=diag.AsDict(), test=suite_key,
              start_revision=revision, end_revision=sys.maxint, name=name)
        elif existing_entity.key.id() != diag.guid:
          raise ValueError(
              name + ' diagnostics must be the same for all histograms')
  return diagnostics.values()


def FindHistogramLevelSparseDiagnostics(guid, histograms):
  hist = histograms.LookupHistogram(guid)
  diagnostics = {}
  for name, diag in hist.diagnostics.iteritems():
    if name in HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES:
      diagnostics[name] = diag
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
  path = '%s/%s' % (suite_path, hist.name)

  tir_label = histogram_helpers.GetTIRLabelFromHistogram(hist)
  if tir_label:
    path += '/' + tir_label

  is_ref = hist.diagnostics.get(reserved_infos.IS_REFERENCE_BUILD.name)
  if is_ref and len(is_ref) == 1:
    is_ref = list(is_ref)[0]

  # If a Histogram represents a summary across multiple stories, then its
  # 'stories' diagnostic will contain the names of all of the stories.
  # If a Histogram is not a summary, then its 'stories' diagnostic will contain
  # the singular name of its story.
  story_name = hist.diagnostics.get(reserved_infos.STORIES.name)
  if story_name and len(story_name) == 1:
    escaped_story_name = add_point.EscapeName(list(story_name)[0])
    path += '/' + escaped_story_name
    if is_ref:
      path += '_ref'
  elif is_ref:
    path += '/ref'

  return path


def _GetMasterBotBenchmarkFromHistogram(hist):
  _CheckRequest(
      reserved_infos.MASTERS.name in hist.diagnostics,
      'Histograms must have "%s" diagnostic' % reserved_infos.MASTERS.name)
  master = hist.diagnostics[reserved_infos.MASTERS.name]
  _CheckRequest(
      len(master) == 1,
      'Histograms must have exactly 1 "%s"' % reserved_infos.MASTERS.name)
  master = list(master)[0]

  _CheckRequest(
      reserved_infos.BOTS.name in hist.diagnostics,
      'Histograms must have "%s" diagnostic' % reserved_infos.BOTS.name)
  bot = hist.diagnostics[reserved_infos.BOTS.name]
  _CheckRequest(
      len(bot) == 1,
      'Histograms must have exactly 1 "%s"' % reserved_infos.BOTS.name)
  bot = list(bot)[0]

  _CheckRequest(
      reserved_infos.BENCHMARKS.name in hist.diagnostics,
      'Histograms must have "%s" diagnostic' % reserved_infos.BENCHMARKS.name)
  benchmark = hist.diagnostics[reserved_infos.BENCHMARKS.name]
  _CheckRequest(
      len(benchmark) == 1,
      'Histograms must have exactly 1 "%s"' % reserved_infos.BENCHMARKS.name)
  benchmark = list(benchmark)[0]

  return master, bot, benchmark


def ComputeRevision(histograms):
  _CheckRequest(len(histograms) > 0, 'Must upload at least one histogram')
  diagnostics = histograms.GetFirstHistogram().diagnostics
  _CheckRequest(reserved_infos.CHROMIUM_COMMIT_POSITIONS.name in diagnostics,
                'Histograms must have Chromium commit position attached')
  chromium_commit_position = list(diagnostics[
      reserved_infos.CHROMIUM_COMMIT_POSITIONS.name])

  _CheckRequest(len(chromium_commit_position) == 1,
                'Chromium commit position must have 1 value')

  # TODO(eakuefner): Allow users to specify other types of revisions to be used
  # for computing revisions of dashboard points. See
  # https://github.com/catapult-project/catapult/issues/3623.
  return chromium_commit_position[0]


def InlineDenseSharedDiagnostics(histograms):
  # TODO(eakuefner): Delete inlined diagnostics from the set
  for hist in histograms:
    diagnostics = hist.diagnostics
    for name, diag in diagnostics.iteritems():
      if name not in SPARSE_DIAGNOSTIC_NAMES:
        diag.Inline()
