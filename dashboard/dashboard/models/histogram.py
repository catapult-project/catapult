# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The datastore models for histograms and diagnostics."""

from google.appengine.ext import ndb

from dashboard.models import graph_data
from dashboard.models import internal_only_model


class JsonModel(internal_only_model.InternalOnlyModel):
  # Similarly to Row, we don't need to memcache these as we don't expect to
  # access them repeatedly.
  _use_memcache = False

  data = ndb.JsonProperty()
  test = ndb.KeyProperty(graph_data.TestMetadata)
  internal_only = ndb.BooleanProperty(default=False, indexed=True)


class Histogram(JsonModel):
  # Needed for timeseries queries (e.g. for alerting).
  revision = ndb.IntegerProperty(indexed=True)


class SparseDiagnostic(JsonModel):
  # Need for intersecting range queries.
  start_revision, end_revision = ndb.IntegerProperty(indexed=True)
