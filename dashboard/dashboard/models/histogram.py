# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The datastore models for histograms and diagnostics."""

import json
import sys

from google.appengine.ext import ndb

from dashboard.models import graph_data
from dashboard.models import internal_only_model


class JsonModel(internal_only_model.InternalOnlyModel):
  # Similarly to Row, we don't need to memcache these as we don't expect to
  # access them repeatedly.
  _use_memcache = False

  data = ndb.JsonProperty(compressed=True)
  test = ndb.KeyProperty(graph_data.TestMetadata)
  internal_only = ndb.BooleanProperty(default=False, indexed=True)


class Histogram(JsonModel):
  # Needed for timeseries queries (e.g. for alerting).
  revision = ndb.IntegerProperty(indexed=True)


class SparseDiagnostic(JsonModel):
  # Need for intersecting range queries.
  name = ndb.StringProperty(indexed=False)
  start_revision = ndb.IntegerProperty(indexed=True)
  end_revision = ndb.IntegerProperty(indexed=True)

  @staticmethod
  @ndb.synctasklet
  def GetMostRecentValuesByNames(test_key, diagnostic_names):
    """Gets the data in the latests sparse diagnostics with the given
       set of diagnostic names.

    Args:
      test_key: The TestKey entity to lookup the diagnotics by
      diagnostic_names: Set of the names of the diagnostics to look up

    Returns:
      A dictionary where the keys are the given names, and the values are the
      corresponding diagnostics' values.
      None if no diagnostics are found with the given keys or type.
    """
    result = yield SparseDiagnostic.GetMostRecentValuesByNamesAsync(
        test_key, diagnostic_names)
    raise ndb.Return(result)

  @staticmethod
  @ndb.tasklet
  def GetMostRecentValuesByNamesAsync(test_key, diagnostic_names):
    diagnostics = yield SparseDiagnostic.query(
        ndb.AND(SparseDiagnostic.end_revision == sys.maxint,
                SparseDiagnostic.test == test_key)).fetch_async()

    diagnostic_map = {}

    for diagnostic in diagnostics:
      if diagnostic.name in diagnostic_names:
        assert diagnostic_map.get(diagnostic.name) is None
        diagnostic_data = json.loads(diagnostic.data)
        diagnostic_map[diagnostic.name] = diagnostic_data.get('values')
    raise ndb.Return(diagnostic_map)
