# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.models import sheriff as sheriff_module


_TASK_QUEUE_NAME = 'deprecate-tests-queue'
_TESTS_PER_QUERY = 100


class CronUpdateSheriffHandler(request_handler.RequestHandler):
  def get(self):
    datastore_hooks.SetPrivilegedRequest()
    _QueryTestsTask(start_cursor=None)

  def post(self):
    datastore_hooks.SetPrivilegedRequest()
    _QueryTestsTask(start_cursor=None)



@ndb.synctasklet
def _QueryTestsTask(start_cursor=None, sheriffs=None, anomaly_configs=None):
  if not sheriffs:
    sheriffs = yield sheriff_module.Sheriff.query().fetch_async()

  if not anomaly_configs:
    anomaly_configs = yield anomaly_config.AnomalyConfig.query().fetch_async()

  q = graph_data.TestMetadata.query()
  q.filter(graph_data.TestMetadata.has_rows == True)
  q.order(graph_data.TestMetadata.key)
  keys, next_cursor, more = q.fetch_page(
      _TESTS_PER_QUERY, start_cursor=start_cursor, keys_only=True)

  if more:
    deferred.defer(
        _QueryTestsTask, start_cursor=next_cursor, _queue=_TASK_QUEUE_NAME)

  yield [_DoTestUpdateSheriff(k, sheriffs, anomaly_configs) for k in keys]


@ndb.tasklet
def _DoTestUpdateSheriff(test_key, sheriffs, anomaly_configs):
  test = yield test_key.get_async()

  changed = yield test.UpdateSheriffAsync(
      sheriffs=sheriffs, anomaly_configs=anomaly_configs)

  if changed:
    yield test.put_async()
