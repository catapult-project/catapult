# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for displaying an overview of jobs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import json
import webapp2

from dashboard.pinpoint.models import job as job_module
from dashboard.common import utils

from google.appengine.datastore import datastore_query

_BATCH_FETCH_TIMEOUT = 200
_MAX_JOBS_TO_FETCH = 100
_MAX_JOBS_TO_COUNT = 1000
_DEFAULT_FILTERED_JOBS = 40


class Error(Exception):
  pass


class InvalidInput(Error):
  pass


class Jobs(webapp2.RequestHandler):
  """Shows an overview of recent anomalies for perf sheriffing."""

  def get(self):
    try:
      self.response.out.write(
          json.dumps(
              _GetJobs(
                  self.request.get_all('o'),
                  self.request.get_all('filter'),
                  self.request.get('prev_cursor', ''),
                  self.request.get('next_cursor', ''),
              )))
    except InvalidInput as e:
      self.response.set_status(400)
      logging.exception(e)
      self.response.out.write(json.dumps({'error': e.message}))


def _GetJobs(options, query_filter, prev_cursor='', next_cursor=''):
  query = job_module.Job.query()

  # Query filters should a string as described in https://google.aip.dev/160
  # We implement a simple parser for the query_filter provided, to allow us to
  # support a simple expression language expressed in the AIP.
  # FIXME: Implement a validating parser.
  def _ParseExpressions():
    # Yield tokens as we parse them.
    # We only support 'AND' as a keyword and ignore any 'OR's.
    for q in query_filter:
      parts = q.split(' ')
      for p in parts:
        if p == 'AND':
          continue
        yield p

  has_filter = False
  has_batch_filter = False
  for f in _ParseExpressions():
    if f.startswith('user='):
      has_filter = True
      query = query.filter(job_module.Job.user == f[len('user='):])
    elif f.startswith('configuration='):
      has_filter = True
      query = query.filter(
          job_module.Job.configuration == f[len('configuration='):])
    elif f.startswith('comparison_mode='):
      has_filter = True
      query = query.filter(
          job_module.Job.comparison_mode == f[len('comparison_mode='):])
    elif f.startswith('batch_id='):
      has_batch_filter = True
      batch_id = f[len('batch_id='):]
      if not batch_id:
        raise InvalidInput('batch_id when specified must not be empty')
      query = query.filter(job_module.Job.batch_id == batch_id)

  if (has_filter or has_batch_filter) and (prev_cursor or next_cursor):
    raise InvalidInput('pagination not supported for filtered queries')

  if has_filter and has_batch_filter:
    raise InvalidInput('batch ids are mutually exclusive with job filters')

  page_size = _MAX_JOBS_TO_FETCH
  timeout_qo = datastore_query.QueryOptions()
  if has_batch_filter:
    timeout_qo = datastore_query.QueryOptions(deadline=_BATCH_FETCH_TIMEOUT)
  elif has_filter:
    page_size = _DEFAULT_FILTERED_JOBS

  count_future = query.count_async(limit=_MAX_JOBS_TO_COUNT, options=timeout_qo)

  if not prev_cursor and not next_cursor:
    jobs, cursor, more = query.order(-job_module.Job.created).fetch_page(
        page_size=page_size, options=timeout_qo)
    prev_cursor = ''
    next_cursor = cursor.urlsafe() if cursor else ''
    prev_ = False
    next_ = True if more else False
  elif next_cursor:
    cursor = datastore_query.Cursor(urlsafe=next_cursor)
    jobs, cursor, more = query.order(-job_module.Job.created).fetch_page(
        page_size=page_size, start_cursor=cursor, options=timeout_qo)
    prev_cursor = next_cursor
    next_cursor = cursor.urlsafe()
    prev_ = True
    next_ = True if more else False
  elif prev_cursor:
    cursor = datastore_query.Cursor(urlsafe=prev_cursor)
    jobs, cursor, more = query.order(job_module.Job.created).fetch_page(
        page_size=page_size, start_cursor=cursor, options=timeout_qo)
    jobs.reverse()
    next_cursor = prev_cursor
    prev_cursor = cursor.urlsafe()
    prev_ = True if more else False
    next_ = True

  result = {
      'jobs': [],
      'count': count_future.get_result(),
      'max_count': _MAX_JOBS_TO_COUNT,
      'prev_cursor': prev_cursor,
      'next_cursor': next_cursor,
      'prev': prev_,
      'next': next_,
  }

  service_account_email = utils.ServiceAccountEmail()
  logging.debug('service account email = %s', service_account_email)

  def _FixupEmails(j):
    user = j.get('user')
    if user and user == service_account_email:
      j['user'] = 'chromeperf (automation)'
    return j

  for job in jobs:
    result['jobs'].append(_FixupEmails(job.AsDict(options)))

  return result
