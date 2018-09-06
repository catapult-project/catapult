# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

import cloudstorage
import json
import logging
import sys
import uuid
import zlib

from google.appengine.api import taskqueue

from dashboard.api import api_request_handler
from dashboard.common import datastore_hooks
from dashboard.common import histogram_helpers
from dashboard.common import request_handler
from dashboard.common import timing
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import reserved_infos

SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES = set([
    reserved_infos.ARCHITECTURES.name,
    reserved_infos.BENCHMARKS.name,
    reserved_infos.BENCHMARK_DESCRIPTIONS.name,
    reserved_infos.BOTS.name,
    reserved_infos.BUG_COMPONENTS.name,
    reserved_infos.DOCUMENTATION_URLS.name,
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
    reserved_infos.RELATED_NAMES.name,
    reserved_infos.STORIES.name,
    reserved_infos.STORYSET_REPEATS.name,
    reserved_infos.STORY_TAGS.name,
])

SPARSE_DIAGNOSTIC_NAMES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES)


TASK_QUEUE_NAME = 'histograms-queue'

_RETRY_PARAMS = cloudstorage.RetryParams(backoff_factor=1.1)
_TASK_RETRY_LIMIT = 4


def _CheckRequest(condition, msg):
  if not condition:
    raise api_request_handler.BadRequestError(msg)


class AddHistogramsProcessHandler(request_handler.RequestHandler):

  def post(self):
    datastore_hooks.SetPrivilegedRequest()

    try:
      params = json.loads(self.request.body)
      gcs_file_path = params['gcs_file_path']

      try:
        gcs_file = cloudstorage.open(
            gcs_file_path, 'r', retry_params=_RETRY_PARAMS)
        contents = gcs_file.read()
        data_str = zlib.decompress(contents)
        gcs_file.close()
      finally:
        cloudstorage.delete(gcs_file_path, retry_params=_RETRY_PARAMS)

      with timing.WallTimeLogger('json.loads'):
        histogram_dicts = json.loads(data_str)

      ProcessHistogramSet(histogram_dicts)
    except Exception as e: # pylint: disable=broad-except
      logging.error('Error processing histograms: %r', e.message)
      self.response.out.write(json.dumps({'error': e.message}))


class AddHistogramsHandler(api_request_handler.ApiRequestHandler):

  def AuthorizedPost(self):
    datastore_hooks.SetPrivilegedRequest()

    with timing.WallTimeLogger('decompress'):
      try:
        data_str = self.request.body
        zlib.decompress(data_str)
        logging.info('Recieved compressed data.')
      except zlib.error:
        data_str = self.request.get('data')
        data_str = zlib.compress(data_str)
        logging.info('Recieved uncompressed data.')

    if not data_str:
      raise api_request_handler.BadRequestError('Missing "data" parameter')

    filename = uuid.uuid4()
    params = {'gcs_file_path': '/add-histograms-cache/%s' % filename}

    gcs_file = cloudstorage.open(
        params['gcs_file_path'], 'w',
        content_type='application/octet-stream',
        retry_params=_RETRY_PARAMS)
    gcs_file.write(data_str)
    gcs_file.close()

    retry_options = taskqueue.TaskRetryOptions(
        task_retry_limit=_TASK_RETRY_LIMIT)
    queue = taskqueue.Queue('default')
    queue.add(
        taskqueue.Task(
            url='/add_histograms/process', payload=json.dumps(params),
            retry_options=retry_options))


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

  with timing.WallTimeLogger('hs.ImportDicts'):
    histograms.ImportDicts(histogram_dicts)

  with timing.WallTimeLogger('hs.ResolveRelatedHistograms'):
    histograms.ResolveRelatedHistograms()

  with timing.WallTimeLogger('hs.DeduplicateDiagnostics'):
    histograms.DeduplicateDiagnostics()

  if len(histograms) == 0:
    raise api_request_handler.BadRequestError(
        'HistogramSet JSON must contain at least one histogram.')

  with timing.WallTimeLogger('hs._LogDebugInfo'):
    _LogDebugInfo(histograms)

  with timing.WallTimeLogger('InlineDenseSharedDiagnostics'):
    InlineDenseSharedDiagnostics(histograms)

  # TODO(eakuefner): Get rid of this.
  # https://github.com/catapult-project/catapult/issues/4242
  with timing.WallTimeLogger('_PurgeHistogramBinData'):
    _PurgeHistogramBinData(histograms)

  with timing.WallTimeLogger('_GetDiagnosticValue calls'):
    master = _GetDiagnosticValue(
        reserved_infos.MASTERS.name, histograms.GetFirstHistogram())
    bot = _GetDiagnosticValue(
        reserved_infos.BOTS.name, histograms.GetFirstHistogram())
    benchmark = _GetDiagnosticValue(
        reserved_infos.BENCHMARKS.name, histograms.GetFirstHistogram())
    benchmark_description = _GetDiagnosticValue(
        reserved_infos.BENCHMARK_DESCRIPTIONS.name,
        histograms.GetFirstHistogram(), optional=True)

  with timing.WallTimeLogger('_ValidateMasterBotBenchmarkName'):
    _ValidateMasterBotBenchmarkName(master, bot, benchmark)

  with timing.WallTimeLogger('ComputeRevision'):
    suite_key = utils.TestKey('%s/%s/%s' % (master, bot, benchmark))

    logging.info('Suite: %s', suite_key.id())

    revision = ComputeRevision(histograms)

    internal_only = graph_data.Bot.GetInternalOnlySync(master, bot)

  revision_record = histogram.HistogramRevisionRecord.GetOrCreate(
      suite_key, revision)
  revision_record.put()

  last_added = histogram.HistogramRevisionRecord.GetLatest(
      suite_key).get_result()

  # On first upload, a query immediately following a put may return nothing.
  if not last_added:
    last_added = revision_record

  _CheckRequest(last_added, 'No last revision')

  # We'll skip the histogram-level sparse diagnostics because we need to
  # handle those with the histograms, below, so that we can properly assign
  # test paths.
  with timing.WallTimeLogger('FindSuiteLevelSparseDiagnostics'):
    suite_level_sparse_diagnostic_entities = FindSuiteLevelSparseDiagnostics(
        histograms, suite_key, revision, internal_only)

  # TODO(eakuefner): Refactor master/bot computation to happen above this line
  # so that we can replace with a DiagnosticRef rather than a full diagnostic.
  with timing.WallTimeLogger('DeduplicateAndPut'):
    new_guids_to_old_diagnostics = (
        histogram.SparseDiagnostic.FindOrInsertDiagnostics(
            suite_level_sparse_diagnostic_entities, suite_key,
            revision, last_added.revision).get_result())

  with timing.WallTimeLogger('ReplaceSharedDiagnostic calls'):
    for new_guid, old_diagnostic in new_guids_to_old_diagnostics.iteritems():
      histograms.ReplaceSharedDiagnostic(
          new_guid, diagnostic.Diagnostic.FromDict(old_diagnostic))

  with timing.WallTimeLogger('_BatchHistogramsIntoTasks'):
    tasks = _BatchHistogramsIntoTasks(
        suite_key.id(), histograms, revision, benchmark_description)

  with timing.WallTimeLogger('_QueueHistogramTasks'):
    _QueueHistogramTasks(tasks)


def _ValidateMasterBotBenchmarkName(master, bot, benchmark):
  for n in (master, bot, benchmark):
    if '/' in n:
      raise api_request_handler.BadRequestError('Illegal slash in %s' % n)


def _QueueHistogramTasks(tasks):
  queue = taskqueue.Queue(TASK_QUEUE_NAME)
  futures = []
  for i in xrange(0, len(tasks), taskqueue.MAX_TASKS_PER_ADD):
    f = queue.add_async(tasks[i:i + taskqueue.MAX_TASKS_PER_ADD])
    futures.append(f)
  for f in futures:
    f.get_result()


def _MakeTask(params):
  return taskqueue.Task(
      url='/add_histograms_queue', payload=json.dumps(params),
      _size_check=False)


def _BatchHistogramsIntoTasks(
    suite_path, histograms, revision, benchmark_description):
  params = []
  tasks = []

  base_size = _MakeTask([]).size
  estimated_size = 0

  duplicate_check = set()

  for hist in histograms:
    diagnostics = FindHistogramLevelSparseDiagnostics(hist)

    # TODO(eakuefner): Don't compute full diagnostics, because we need anyway to
    # call GetOrCreate here and in the queue.
    test_path = '%s/%s' % (suite_path, histogram_helpers.ComputeTestPath(hist))

    if test_path in duplicate_check:
      raise api_request_handler.BadRequestError(
          'Duplicate histogram detected: %s' % test_path)
    duplicate_check.add(test_path)

    # TODO(eakuefner): Batch these better than one per task.
    task_dict = _MakeTaskDict(
        hist, test_path, revision, benchmark_description, diagnostics)

    estimated_size_dict = len(json.dumps(task_dict))
    estimated_size += estimated_size_dict

    # Creating the task directly and getting the size back is slow, so we just
    # keep a running total of estimated task size. A bit hand-wavy but the #
    # of histograms per task doesn't need to be perfect, just has to be under
    # the max task size.
    estimated_total_size = estimated_size * 1.05 + base_size + 1024
    if estimated_total_size > taskqueue.MAX_TASK_SIZE_BYTES:
      t = _MakeTask(params)
      tasks.append(t)
      params = []
      estimated_size = estimated_size_dict

    params.append(task_dict)

  if params:
    t = _MakeTask(params)
    tasks.append(t)

  return tasks


def _MakeTaskDict(
    hist, test_path, revision, benchmark_description, diagnostics):
  # TODO(simonhatch): "revision" is common to all tasks, as is the majority of
  # the test path
  params = {
      'test_path': test_path,
      'revision': revision,
      'benchmark_description': benchmark_description
  }

  # By changing the GUID just before serializing the task, we're making it
  # unique for each histogram. This avoids each histogram trying to write the
  # same diagnostic out (datastore contention), at the cost of copyin the
  # data. These are sparsely written to datastore anyway, so the extra
  # storage should be minimal.
  for d in diagnostics.itervalues():
    d.ResetGuid()

  diagnostics = {k: d.AsDict() for k, d in diagnostics.iteritems()}

  params['diagnostics'] = diagnostics
  params['data'] = hist.AsDict()

  return params


def FindSuiteLevelSparseDiagnostics(
    histograms, suite_key, revision, internal_only):
  diagnostics = {}
  for hist in histograms:
    for name, diag in hist.diagnostics.iteritems():
      if name in SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES:
        existing_entity = diagnostics.get(name)
        if existing_entity is None:
          diagnostics[name] = histogram.SparseDiagnostic(
              id=diag.guid, data=diag.AsDict(), test=suite_key,
              start_revision=revision, end_revision=sys.maxint, name=name,
              internal_only=internal_only)
        elif existing_entity.key.id() != diag.guid:
          raise ValueError(
              name + ' diagnostics must be the same for all histograms')
  return diagnostics.values()


def FindHistogramLevelSparseDiagnostics(hist):
  diagnostics = {}
  for name, diag in hist.diagnostics.iteritems():
    if name in HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES:
      diagnostics[name] = diag
  return diagnostics


def _GetDiagnosticValue(name, hist, optional=False):
  if optional:
    if name not in hist.diagnostics:
      return None

  _CheckRequest(
      name in hist.diagnostics,
      'Histogram [%s] missing "%s" diagnostic' % (hist.name, name))
  value = hist.diagnostics[name]
  _CheckRequest(
      len(value) == 1,
      'Histograms must have exactly 1 "%s"' % name)
  return value.GetOnlyElement()


def ComputeRevision(histograms):
  _CheckRequest(len(histograms) > 0, 'Must upload at least one histogram')
  rev = _GetDiagnosticValue(
      reserved_infos.POINT_ID.name,
      histograms.GetFirstHistogram(), optional=True)

  if rev is None:
    rev = _GetDiagnosticValue(
        reserved_infos.CHROMIUM_COMMIT_POSITIONS.name,
        histograms.GetFirstHistogram())

  if not isinstance(rev, (long, int)):
    raise api_request_handler.BadRequestError(
        'Point ID must be an integer.')

  return rev


def InlineDenseSharedDiagnostics(histograms):
  # TODO(eakuefner): Delete inlined diagnostics from the set
  for hist in histograms:
    diagnostics = hist.diagnostics
    for name, diag in diagnostics.iteritems():
      if name not in SPARSE_DIAGNOSTIC_NAMES:
        diag.Inline()


def _PurgeHistogramBinData(histograms):
  # We do this because RelatedEventSet and Breakdown data in bins is
  # enormous in their current implementation.
  for cur_hist in histograms:
    for cur_bin in cur_hist.bins:
      for dm in cur_bin.diagnostic_maps:
        keys = dm.keys()
        for k in keys:
          del dm[k]
