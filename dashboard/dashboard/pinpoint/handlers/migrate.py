# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import logging

from google.appengine.api import datastore_errors
from google.appengine.datastore import datastore_query
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard.api import api_request_handler
from dashboard.common import stored_object
from dashboard.common import utils
from dashboard.pinpoint.models import job


_BATCH_SIZE = 10
_STATUS_KEY = 'job_migration_status'


class Migrate(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    self._CheckIsLoggedIn()
    if not utils.IsAdministrator():
      raise api_request_handler.ForbiddenError()

  def Get(self):
    return stored_object.Get(_STATUS_KEY) or {}

  def Post(self):
    status = stored_object.Get(_STATUS_KEY)

    if not status:
      _Start()
    return self.Get()

def _Start():
  query = job.Job.query(job.Job.task == None)
  status = {
      'count': 0,
      'started': datetime.datetime.now().isoformat(),
      'total': query.count(),
  }
  stored_object.Set(_STATUS_KEY, status)
  deferred.defer(_Migrate, status, None)

def _Migrate(status, cursor=None):
  if cursor:
    cursor = datastore_query.Cursor(urlsafe=cursor)
  query = job.Job.query(job.Job.task == None)
  jobs, next_cursor, more = query.fetch_page(_BATCH_SIZE, start_cursor=cursor)

  try:
    ndb.put_multi(jobs)
  except datastore_errors.BadRequestError as e:
    logging.critical(e)
    logging.critical([j.job_id for j in jobs])

  if more:
    status['count'] += len(jobs)
    stored_object.Set(_STATUS_KEY, status)

    deferred.defer(_Migrate, status, next_cursor.urlsafe())
  else:
    stored_object.Set(_STATUS_KEY, None)
