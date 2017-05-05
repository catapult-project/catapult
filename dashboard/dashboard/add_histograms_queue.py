# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to add new histograms to the datastore."""

import json

from dashboard import add_histograms
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
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
    data_dict = json.loads(data)
    revision = int(self.request.get('revision'))
    test_key = utils.TestKey(self.request.get('test_path'))
    guid = data_dict['guid']

    if data_dict.get('type') in add_histograms.SPARSE_DIAGNOSTIC_TYPES:
      entity = histogram.SparseDiagnostic(
          id=guid, data=data, test=test_key, start_revision=revision,
          end_revision=revision)
    else:
      entity = histogram.Histogram(
          id=guid, data=data, test=test_key, revision=revision)

    entity.put()
