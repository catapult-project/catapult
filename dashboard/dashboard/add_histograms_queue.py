# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to add new histograms to the datastore."""

import json

# TODO(eakuefner): Move these helpers so we don't have to import add_point_queue
# directly.
from dashboard import add_point_queue
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import stored_object
from dashboard.models import anomaly
from dashboard.models import histogram

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
      entity = histogram.Histogram(
          id=guid, data=data, test=test_key, revision=revision,
          internal_only=internal_only)

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
