# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A cron job which queues old tests for deletion."""

import datetime
import logging

from google.appengine.api import taskqueue
from google.appengine.datastore import datastore_query

from dashboard import datastore_hooks
from dashboard import list_tests
from dashboard import request_handler
from dashboard import utils
from dashboard.models import graph_data

_CUTOFF_DATE = datetime.timedelta(days=183)  # Six months ago
_TESTS_TO_CHECK_AT_ONCE = 100

# Queue name needs to be listed in queue.yaml.
_TASK_QUEUE_NAME = 'delete-old-tests-queue'
_DELETE_TASK_QUEUE_NAME = 'delete-tests-queue'


class DeleteOldTestsHandler(request_handler.RequestHandler):
  """Finds tests with no new data, and deletes them."""

  def get(self):
    self.post()

  def post(self):
    """Query for tests, and put ones with no new data on the delete queue."""
    datastore_hooks.SetPrivilegedRequest()
    logging.info('Cursor: %s', self.request.get('cursor'))
    cursor = datastore_query.Cursor(urlsafe=self.request.get('cursor'))
    tests, next_cursor, more = graph_data.TestMetadata.query().fetch_page(
        _TESTS_TO_CHECK_AT_ONCE, keys_only=True, start_cursor=cursor)
    for test in tests:
      # Delete this test if:
      # 1) It has no Rows newer than the cutoff
      # 2) It has no descendant tests
      logging.info('Checking %s', utils.TestPath(test))
      no_new_rows = False
      last_row = graph_data.Row.query(
          graph_data.Row.parent_test == utils.OldStyleTestKey(test)).order(
              -graph_data.Row.timestamp).get()
      if last_row:
        if last_row.timestamp < datetime.datetime.today() - _CUTOFF_DATE:
          no_new_rows = True
      else:
        no_new_rows = True
      descendants = list_tests.GetTestDescendants(test, keys_only=True)
      if test in descendants:
        descendants.remove(test)
      stamp = 'never'
      if last_row:
        stamp = last_row.timestamp
      if not descendants and no_new_rows:
        logging.info('Deleting test %s last timestamp %s',
                     utils.TestPath(test), stamp)
        taskqueue.add(
            url='/delete_test_data',
            params={
                'test_path': utils.TestPath(test),  # For manual inspection.
                'test_key': test.urlsafe(),
            },
            queue_name=_DELETE_TASK_QUEUE_NAME)
      else:
        logging.info('NOT Deleting test %s last timestamp %s',
                     utils.TestPath(test), stamp)

    if more:
      taskqueue.add(
          url='/delete_old_tests',
          params={'cursor': next_cursor.urlsafe()},
          queue_name=_TASK_QUEUE_NAME)
