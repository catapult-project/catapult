# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to add new histograms to the datastore."""

import json
import sys

# TODO(eakuefner): Move these helpers so we don't have to import add_point or
# add_point_queue directly.
from dashboard import add_histograms
from dashboard import add_point
from dashboard import add_point_queue
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import stored_object
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic_ref


REVISION_FIELDS_TO_ANNOTATION_NAMES = {
    'chromium_commit_position': 'r_chromium_commit_pos',
    'v8_commit_position': 'r_v8_rev',
    'chromium': 'r_chromium_git',
    'v8': 'r_v8_git',
    # TODO(eakuefner): Add r_catapult_git to Dashboard revision_info map (see
    # https://github.com/catapult-project/catapult/issues/3545).
    'catapult': 'r_catapult_git',
    'angle': 'r_angle_git',
    'webrtc': 'r_webrtc_git'
}


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

    data = self.request.get('data')
    revision = int(self.request.get('revision'))
    test_path = self.request.get('test_path')

    data_dict = json.loads(data)
    guid = data_dict['guid']
    is_diagnostic = 'type' in data_dict

    test_path_parts = test_path.split('/')
    master = test_path_parts[0]
    bot = test_path_parts[1]
    test_name = '/'.join(test_path_parts[2:])
    bot_whitelist = stored_object.Get(add_point_queue.BOT_WHITELIST_KEY)
    internal_only = add_point_queue.BotInternalOnly(bot, bot_whitelist)
    extra_args = {} if is_diagnostic else GetUnitArgs(data_dict['unit'])
    # TDOO(eakuefner): Populate benchmark_description once it appears in
    # diagnostics.
    test_key = add_point_queue.GetOrCreateAncestors(
        master, bot, test_name, internal_only, **extra_args).key

    if is_diagnostic:
      entity = histogram.SparseDiagnostic(
          id=guid, data=data, test=test_key, start_revision=revision,
          end_revision=revision, internal_only=internal_only)
    else:
      diagnostics = self.request.get('diagnostics')
      if diagnostics:
        diagnostic_data = json.loads(diagnostics)
        diagnostic_entities = []
        for diagnostic_datum in diagnostic_data:
          # TODO(eakuefner): Pass map of guid to dict to avoid overhead
          guid = diagnostic_datum['guid']
          diagnostic_entities.append(histogram.SparseDiagnostic(
              id=guid, data=diagnostic_datum, test=test_key,
              start_revision=revision, end_revision=sys.maxint,
              internal_only=internal_only))
        new_guids_to_existing_diagnostics = add_histograms.DeduplicateAndPut(
            diagnostic_entities, test_key, revision).iteritems()
        # TODO(eakuefner): Move per-histogram monkeypatching logic to Histogram.
        hs = histogram_set.HistogramSet()
        hs.ImportDicts([data_dict])
        # TODO(eakuefner): Share code for replacement logic with add_histograms
        for new_guid, existing_diagnostic in new_guids_to_existing_diagnostics:
          hs.ReplaceSharedDiagnostic(
              new_guid, diagnostic_ref.DiagnosticRef(
                  existing_diagnostic['guid']))
        data = hs.GetFirstHistogram().AsDict()

      entity = histogram.Histogram(
          id=guid, data=data, test=test_key, revision=revision,
          internal_only=internal_only)
      AddRow(data_dict, test_key, revision, test_path, internal_only)

    entity.put()

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


def AddRow(histogram_dict, test_metadata_key, revision, test_path,
           internal_only):
  h = histogram_module.Histogram.FromDict(histogram_dict)
  # TODO(eakuefner): Move this check into _PopulateNumericalFields once we
  # know that it's okay to put rows that don't have a value/error (see
  # https://github.com/catapult-project/catapult/issues/3564).
  if h.num_values == 0:
    return
  row_dict = _MakeRowDict(revision, test_path, h)
  properties = add_point.GetAndValidateRowProperties(row_dict)
  test_container_key = utils.GetTestContainerKey(test_metadata_key)
  row = graph_data.Row(id=revision, parent=test_container_key,
                       internal_only=internal_only, **properties)
  row.put()

def _MakeRowDict(revision, test_path, tracing_histogram):
  d = {}
  # TODO(#3563): Wire up a_tracing_uri.
  test_parts = test_path.split('/')
  d['master'] = test_parts[0]
  d['bot'] = test_parts[1]
  d['test'] = '/'.join(test_parts[2:])
  d['revision'] = revision
  d['supplemental_columns'] = {}

  revision_info = tracing_histogram.diagnostics['revisions']
  for attribute, annotation in REVISION_FIELDS_TO_ANNOTATION_NAMES.iteritems():
    value = getattr(revision_info, attribute)
    # TODO(eakuefner): Formalize unique-per-upload diagnostics to make this
    # check an earlier error. RevisionInfo's fields have to be lists, but there
    # should be only one revision of each type per upload.
    if not value:
      continue
    _CheckRequest(
        isinstance(value, list) and len(value) == 1,
        'RevisionInfo fields must contain at most one revision')

    d['supplemental_columns'][annotation] = value[0]

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
