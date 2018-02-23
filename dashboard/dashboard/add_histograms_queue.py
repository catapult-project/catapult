# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to add new histograms to the datastore."""

import json
import logging
import sys

from google.appengine.ext import ndb

# TODO(eakuefner): Move these helpers so we don't have to import add_point or
# add_point_queue directly.
from dashboard import add_histograms
from dashboard import add_point
from dashboard import add_point_queue
from dashboard import find_anomalies
from dashboard import graph_revisions
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import stored_object
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import diagnostic_ref
from tracing.value.diagnostics import reserved_infos

DIAGNOSTIC_NAMES_TO_ANNOTATION_NAMES = {
    reserved_infos.LOG_URLS.name: 'a_stdio_url',
    reserved_infos.CHROMIUM_COMMIT_POSITIONS.name: 'r_chromium_commit_pos',
    reserved_infos.V8_COMMIT_POSITIONS.name: 'r_v8_rev',
    reserved_infos.CHROMIUM_REVISIONS.name: 'r_chromium_git',
    reserved_infos.V8_REVISIONS.name: 'r_v8_git',
    # TODO(eakuefner): Add r_catapult_git to Dashboard revision_info map (see
    # https://github.com/catapult-project/catapult/issues/3545).
    reserved_infos.CATAPULT_REVISIONS.name: 'r_catapult_git',
    reserved_infos.ANGLE_REVISIONS.name: 'r_angle_git',
    reserved_infos.WEBRTC_REVISIONS.name: 'r_webrtc_git'
}


# List of non-TBMv2 chromium.perf Telemetry benchmarks
LEGACY_BENCHMARKS = [
    'blink_perf.bindings',
    'blink_perf.canvas',
    'blink_perf.css',
    'blink_perf.dom',
    'blink_perf.events',
    'blink_perf.image_decoder',
    'blink_perf.layout',
    'blink_perf.owp_storage',
    'blink_perf.paint',
    'blink_perf.parser',
    'blink_perf.shadow_dom',
    'blink_perf.svg',
    'cronet_perf_tests',
    'dromaeo',
    'dummy_benchmark.noisy_benchmark_1',
    'dummy_benchmark.stable_benchmark_1',
    'jetstream',
    'kraken',
    'octane',
    'rasterize_and_record_micro.partial_invalidation',
    'rasterize_and_record_micro.top_25',
    'scheduler.tough_scheduling_cases',
    'smoothness.desktop_tough_pinch_zoom_cases',
    'smoothness.gpu_rasterization.polymer',
    'smoothness.gpu_rasterization.top_25_smooth',
    'smoothness.gpu_rasterization.tough_filters_cases',
    'smoothness.gpu_rasterization.tough_path_rendering_cases',
    'smoothness.gpu_rasterization.tough_pinch_zoom_cases',
    'smoothness.gpu_rasterization.tough_scrolling_cases',
    'smoothness.gpu_rasterization_and_decoding.image_decoding_cases',
    'smoothness.image_decoding_cases',
    'smoothness.key_desktop_move_cases',
    'smoothness.key_mobile_sites_smooth',
    'smoothness.key_silk_cases',
    'smoothness.maps',
    'smoothness.pathological_mobile_sites',
    'smoothness.simple_mobile_sites',
    'smoothness.sync_scroll.key_mobile_sites_smooth',
    'smoothness.top_25_smooth',
    'smoothness.tough_ad_cases',
    'smoothness.tough_animation_cases',
    'smoothness.tough_canvas_cases',
    'smoothness.tough_filters_cases',
    'smoothness.tough_image_decode_cases',
    'smoothness.tough_path_rendering_cases',
    'smoothness.tough_pinch_zoom_cases',
    'smoothness.tough_scrolling_cases',
    'smoothness.tough_texture_upload_cases',
    'smoothness.tough_webgl_ad_cases',
    'smoothness.tough_webgl_cases',
    'speedometer',
    'speedometer-future',
    'speedometer2',
    'speedometer2-future',
    'start_with_url.cold.startup_pages',
    'start_with_url.warm.startup_pages',
    'thread_times.key_hit_test_cases',
    'thread_times.key_idle_power_cases',
    'thread_times.key_mobile_sites_smooth',
    'thread_times.key_noop_cases',
    'thread_times.key_silk_cases',
    'thread_times.simple_mobile_sites',
    'thread_times.tough_compositor_cases',
    'thread_times.tough_scrolling_cases',
    'v8.detached_context_age_in_gc'
]


STATS_BLACKLIST = ['std', 'count', 'max', 'min', 'sum']


V8_WHITELIST = [
    'v8-gc-full-mark-compactor',
    'v8-gc-incremental-finalize',
    'v8-gc-incremental-step',
    'v8-gc-latency-mark-compactor',
    'v8-gc-memory-mark-compactor',
    'v8-gc-scavenger',
    'v8-gc-total',
]


class BadRequestError(Exception):
  pass


def _CheckRequest(condition, msg):
  if not condition:
    raise BadRequestError(msg)


class AddHistogramsQueueHandler(request_handler.RequestHandler):
  """Request handler to process a histogram and add it to the datastore.

  This request handler is intended to be used only by requests using the
  task queue; it shouldn't be directly from outside.
  """

  def get(self):
    self.post()

  def post(self):
    """Adds a single histogram or sparse shared diagnostic to the datastore.

    The |data| request parameter can be either a histogram or a sparse shared
    diagnostic; the set of diagnostics that are considered sparse (meaning that
    they don't normally change on every upload for a given benchmark from a
    given bot) is shown in add_histograms.SPARSE_DIAGNOSTIC_TYPES.

    See https://goo.gl/lHzea6 for detailed information on the JSON format for
    histograms and diagnostics.

    Request parameters:
      data: JSON encoding of a histogram or shared diagnostic.
      revision: a revision, given as an int.
      test_path: the test path to which this diagnostic or histogram should be
          attached.
    """
    datastore_hooks.SetPrivilegedRequest()

    bot_whitelist_future = stored_object.GetAsync(
        add_point_queue.BOT_WHITELIST_KEY)

    params = json.loads(self.request.body)

    _PrewarmGets(params)

    bot_whitelist = bot_whitelist_future.get_result()

    # Roughly, the processing of histograms and the processing of rows can be
    # done in parallel since there are no dependencies.

    futures = []

    for p in params:
      futures.extend(_ProcessRowAndHistogram(p, bot_whitelist))

    ndb.Future.wait_all(futures)


def _GetStoryFromDiagnosticsDict(diagnostics):
  if not diagnostics:
    return None

  story_name = diagnostics.get(reserved_infos.STORIES.name)
  if not story_name:
    return None

  # TODO(simonhatch): Use GenericSetGetOnlyElement when it's available
  # https://github.com/catapult-project/catapult/issues/4110
  story_name = diagnostic.Diagnostic.FromDict(story_name)
  if story_name and len(story_name) == 1:
    return list(story_name)[0]
  return None


def _PrewarmGets(params):
  keys = set()

  for p in params:
    test_path = p['test_path']
    path_parts = test_path.split('/')

    keys.add(ndb.Key('Master', path_parts[0]))
    keys.add(ndb.Key('Bot', path_parts[1]))

    test_parts = path_parts[2:]
    test_key = '%s/%s' % (path_parts[0], path_parts[1])
    for p in test_parts:
      test_key += '/%s' % p
      keys.add(ndb.Key('TestMetadata', test_key))

  ndb.get_multi_async(list(keys))


def _ProcessRowAndHistogram(params, bot_whitelist):
  revision = int(params['revision'])
  test_path = params['test_path']
  benchmark_description = params['benchmark_description']
  data_dict = params['data']

  logging.info('Processing: %s', test_path)

  hist = histogram_module.Histogram.FromDict(data_dict)
  test_path_parts = test_path.split('/')
  master = test_path_parts[0]
  bot = test_path_parts[1]
  benchmark_name = test_path_parts[2]
  histogram_name = test_path_parts[3]
  if len(test_path_parts) > 4:
    rest = '/'.join(test_path_parts[4:])
  else:
    rest = None
  full_test_name = '/'.join(test_path_parts[2:])
  internal_only = add_point_queue.BotInternalOnly(bot, bot_whitelist)
  extra_args = GetUnitArgs(hist.unit)

  unescaped_story_name = _GetStoryFromDiagnosticsDict(params.get('diagnostics'))

  # TDOO(eakuefner): Populate benchmark_description once it appears in
  # diagnostics.
  # https://github.com/catapult-project/catapult/issues/4096
  parent_test = add_point_queue.GetOrCreateAncestors(
      master, bot, full_test_name, internal_only=internal_only,
      unescaped_story_name=unescaped_story_name,
      benchmark_description=benchmark_description, **extra_args)
  test_key = parent_test.key

  statistics_scalars = hist.statistics_scalars
  legacy_parent_tests = {}

  # TODO(#4213): Stop doing this.
  if benchmark_name in LEGACY_BENCHMARKS:
    statistics_scalars = {}

  for stat_name, scalar in statistics_scalars.iteritems():
    if _ShouldFilter(histogram_name, benchmark_name, stat_name):
      continue
    extra_args = GetUnitArgs(scalar.unit)
    suffixed_name = '%s/%s_%s' % (
        benchmark_name, histogram_name, stat_name)
    if rest is not None:
      suffixed_name += '/' + rest
    legacy_parent_tests[stat_name] = add_point_queue.GetOrCreateAncestors(
        master, bot, suffixed_name, internal_only=internal_only,
        unescaped_story_name=unescaped_story_name, **extra_args)

  return [
      _AddRowsFromData(params, revision, parent_test, legacy_parent_tests,
                       internal_only),
      _AddHistogramFromData(params, revision, test_key, internal_only)]


def _ShouldFilter(test_name, benchmark_name, stat_name):
  if benchmark_name.startswith('memory') or benchmark_name.startswith('media'):
    if 'memory:' in test_name and stat_name in STATS_BLACKLIST:
      return True
  if benchmark_name.startswith('system_health'):
    if stat_name in STATS_BLACKLIST:
      return True
  if benchmark_name.startswith('v8.browsing'):
    if 'memory:unknown_browser' in test_name or 'memory:chrome' in test_name:
      is_from_renderer_processes = 'render_processes' in test_name
      return not is_from_renderer_processes and stat_name in STATS_BLACKLIST
    if 'v8-gc' in test_name:
      return not test_name in V8_WHITELIST and stat_name in STATS_BLACKLIST
  return False

@ndb.tasklet
def _AddRowsFromData(params, revision, parent_test, legacy_parent_tests,
                     internal_only):
  data_dict = params['data']
  test_key = parent_test.key

  stat_names_to_test_keys = {k: v.key for k, v in
                             legacy_parent_tests.iteritems()}
  rows = AddRows(data_dict, test_key, stat_names_to_test_keys, revision,
                 internal_only)
  if not rows:
    print "FOOBAR"
    raise ndb.Return()

  yield ndb.put_multi_async(rows)

  tests_keys = []
  is_monitored = parent_test.sheriff and parent_test.has_rows
  if is_monitored:
    tests_keys.append(parent_test.key)

  for legacy_parent_test in legacy_parent_tests.itervalues():
    is_monitored = legacy_parent_test.sheriff and legacy_parent_test.has_rows
    if is_monitored:
      tests_keys.append(legacy_parent_test.key)

  tests_keys = [
      k for k in tests_keys if not add_point_queue.IsRefBuild(k)]

  # Updating of the cached graph revisions should happen after put because
  # it requires the new row to have a timestamp, which happens upon put.
  futures = [
      graph_revisions.AddRowsToCacheAsync(rows),
      find_anomalies.ProcessTestsAsync(tests_keys)]
  yield futures


@ndb.tasklet
def _AddHistogramFromData(params, revision, test_key, internal_only):
  data_dict = params['data']
  guid = data_dict['guid']
  diagnostics = params.get('diagnostics')
  new_guids_to_existing_diagnostics = yield ProcessDiagnostics(
      diagnostics, revision, test_key, internal_only)

  # TODO(eakuefner): Move per-histogram monkeypatching logic to Histogram.
  hs = histogram_set.HistogramSet()
  hs.ImportDicts([data_dict])
  # TODO(eakuefner): Share code for replacement logic with add_histograms
  for new_guid, existing_diagnostic in (
      new_guids_to_existing_diagnostics.iteritems()):
    hs.ReplaceSharedDiagnostic(
        new_guid, diagnostic_ref.DiagnosticRef(
            existing_diagnostic['guid']))
  data = hs.GetFirstHistogram().AsDict()

  entity = histogram.Histogram(
      id=guid, data=data, test=test_key, revision=revision,
      internal_only=internal_only)
  yield entity.put_async()


@ndb.tasklet
def ProcessDiagnostics(diagnostic_data, revision, test_key, internal_only):
  if not diagnostic_data:
    raise ndb.Return({})

  diagnostic_entities = []
  for name, diagnostic_datum in diagnostic_data.iteritems():
    # TODO(eakuefner): Pass map of guid to dict to avoid overhead
    guid = diagnostic_datum['guid']
    diagnostic_entities.append(histogram.SparseDiagnostic(
        id=guid, name=name, data=diagnostic_datum, test=test_key,
        start_revision=revision, end_revision=sys.maxint,
        internal_only=internal_only))
  new_guids_to_existing_diagnostics = yield (
      add_histograms.DeduplicateAndPutAsync(
          diagnostic_entities, test_key, revision))

  raise ndb.Return(new_guids_to_existing_diagnostics)


def GetUnitArgs(unit):
  unit_args = {
      'units': unit
  }
  # TODO(eakuefner): Port unit system to Python and use that here
  histogram_improvement_direction = unit.split('_')[-1]
  if histogram_improvement_direction == 'biggerIsBetter':
    unit_args['improvement_direction'] = anomaly.UP
  elif histogram_improvement_direction == 'smallerIsBetter':
    unit_args['improvement_direction'] = anomaly.DOWN
  else:
    unit_args['improvement_direction'] = anomaly.UNKNOWN
  return unit_args


def AddRows(histogram_dict, test_metadata_key, stat_names_to_test_keys,
            revision, internal_only):
  h = histogram_module.Histogram.FromDict(histogram_dict)
  # TODO(eakuefner): Move this check into _PopulateNumericalFields once we
  # know that it's okay to put rows that don't have a value/error (see
  # https://github.com/catapult-project/catapult/issues/3564).
  if h.num_values == 0:
    return None

  rows = []

  row_dict = _MakeRowDict(revision, test_metadata_key.id(), h)
  properties = add_point.GetAndValidateRowProperties(row_dict)
  test_container_key = utils.GetTestContainerKey(test_metadata_key)
  rows.append(graph_data.Row(id=revision, parent=test_container_key,
                             internal_only=internal_only, **properties))

  for stat_name, suffixed_key in stat_names_to_test_keys.iteritems():
    row_dict = _MakeRowDict(revision, suffixed_key.id(), h, stat_name=stat_name)
    properties = add_point.GetAndValidateRowProperties(row_dict)
    test_container_key = utils.GetTestContainerKey(suffixed_key)
    rows.append(graph_data.Row(
        id=revision, parent=suffixed_key, internal_only=internal_only,
        **properties))

  return rows

def _MakeRowDict(revision, test_path, tracing_histogram, stat_name=None):
  d = {}
  test_parts = test_path.split('/')
  d['master'] = test_parts[0]
  d['bot'] = test_parts[1]
  d['test'] = '/'.join(test_parts[2:])
  d['revision'] = revision
  d['supplemental_columns'] = {}

  # TODO(#3628): Remove this annotation when the frontend displays the full
  # histogram and all its diagnostics including the full set of trace urls.
  trace_url_set = tracing_histogram.diagnostics.get(
      reserved_infos.TRACE_URLS.name)
  if trace_url_set:
    d['supplemental_columns']['a_tracing_uri'] = list(trace_url_set)[0]

  for diag_name, annotation in DIAGNOSTIC_NAMES_TO_ANNOTATION_NAMES.iteritems():
    revision_info = tracing_histogram.diagnostics.get(diag_name)
    value = list(revision_info) if revision_info else None
    # TODO(eakuefner): Formalize unique-per-upload diagnostics to make this
    # check an earlier error. RevisionInfo's fields have to be lists, but there
    # should be only one revision of each type per upload.
    if not value:
      continue
    _CheckRequest(
        len(value) == 1,
        'RevisionInfo fields must contain at most one revision')

    d['supplemental_columns'][annotation] = value[0]

  if stat_name is not None:
    d['value'] = tracing_histogram.statistics_scalars[stat_name].value
    if stat_name == 'avg':
      d['error'] = tracing_histogram.standard_deviation
  else:
    _PopulateNumericalFields(d, tracing_histogram)
  return d

def _PopulateNumericalFields(row_dict, tracing_histogram):
  statistics_scalars = tracing_histogram.statistics_scalars
  for name, scalar in statistics_scalars.iteritems():
    # We'll skip avg/std since these are already stored as value/error in rows.
    if name in ('avg', 'std'):
      continue

    row_dict['supplemental_columns']['d_%s' % name] = scalar.value

  row_dict['value'] = tracing_histogram.average
  row_dict['error'] = tracing_histogram.standard_deviation
