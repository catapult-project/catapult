# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import os
import time

import webapp2

from google.appengine.api import runtime as apiruntime
from google.appengine.ext import ndb

from infra_libs.ts_mon import shared
from infra_libs.ts_mon.common import distribution
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import metrics


def find_gaps(num_iter):
  """Generate integers not present in an iterable of integers.

  Caution: this is an infinite generator.
  """
  next_num = -1
  for n in num_iter:
    next_num += 1
    while next_num < n:
      yield next_num
      next_num += 1
  while True:
    next_num += 1
    yield next_num


def _assign_task_num(time_fn=datetime.datetime.utcnow):
  expired_keys = []
  unassigned = []
  used_task_nums = []
  time_now = time_fn()
  expired_time = time_now - datetime.timedelta(
      seconds=shared.INSTANCE_EXPIRE_SEC)
  for entity in shared.Instance.query():
    # Don't reassign expired task_num right away to avoid races.
    if entity.task_num >= 0:
      used_task_nums.append(entity.task_num)
    # At the same time, don't assign task_num to expired entities.
    if entity.last_updated < expired_time:
      expired_keys.append(entity.key)
      shared.expired_counter.increment()
      logging.debug(
          'Expiring %s task_num %d, inactive for %s',
          entity.key.id(), entity.task_num,
          time_now - entity.last_updated)
    elif entity.task_num < 0:
      shared.started_counter.increment()
      unassigned.append(entity)

  logging.debug('Found %d expired and %d unassigned instances',
                len(expired_keys), len(unassigned))

  used_task_nums = sorted(used_task_nums)
  for entity, task_num in zip(unassigned, find_gaps(used_task_nums)):
    entity.task_num = task_num
    logging.debug('Assigned %s task_num %d', entity.key.id(), task_num)
  futures_unassigned = ndb.put_multi_async(unassigned)
  futures_expired = ndb.delete_multi_async(expired_keys)
  ndb.Future.wait_all(futures_unassigned + futures_expired)
  logging.debug('Committed all changes')


class SendHandler(webapp2.RequestHandler):
  def get(self):
    if self.request.headers.get('X-Appengine-Cron') != 'true':
      self.abort(403)

    with shared.instance_namespace_context():
      _assign_task_num()

    interface.invoke_global_callbacks()


class TSMonJSHandler(webapp2.RequestHandler):
  """Proxy handler for ts_mon metrics collected in JavaScript.

  To use this class:
  1. Subclass it and override self.xsrf_is_valid
  2. After instantiation call self.register_metrics to register global metrics.
  """

  def __init__(self, request=None, response=None):
    super(TSMonJSHandler, self).__init__(request, response)
    self._metrics = None

  def register_metrics(self, metrics_list):
    """Registers ts_mon metrics, required for use.

    Args:
      metrics_list: a list of definitions, from ts_mon.metrics.
    """
    interface.register_global_metrics(metrics_list)
    self._metrics = self._metrics or {}
    for metric in metrics_list:
      if metric.is_cumulative():
        metric.dangerously_enable_cumulative_set()
      self._metrics[metric.name] = metric

  def post(self):
    """POST expects a JSON body that's a dict which includes a key "metrics".
    This key's value is an array of objects with schema:
    {
      "metrics": [{
        "MetricInfo": {
          "Name": "monorail/frontend/float_test",
          "ValueType": 2
        },
        "Cells": [{
          "value": 1,
          "fields": {},
          "start_time": 1538430628174
        }]
      }]
    }

    Important!
    The user of this library is responsible for validating XSRF tokens via
    implementing the method self.xsrf_is_valid.
    """
    if not self._metrics:
      self.response.set_status(400)
      self.response.write('No metrics have been registered.')
      logging.warning('gae_ts_mon error: No metrics have been registered.')
      return

    try:
      body = json.loads(self.request.body)
    except ValueError:
      self.response.set_status(400)
      self.response.write('Invalid JSON.')
      logging.warning('gae_ts_mon error: Invalid JSON.')
      return

    if not self.xsrf_is_valid(body):
      self.response.set_status(403)
      self.response.write('XSRF token invalid.')
      logging.warning('gae_ts_mon error: XSRF token invalid.')
      return

    if not isinstance(body, dict):
      self.response.set_status(400)
      self.response.write('Body must be a dictionary.')
      logging.warning('gae_ts_mon error: Body must be a dictionary.')
      return

    if 'metrics' not in body:
      self.response.set_status(400)
      self.response.write('Key "metrics" must be in body.')
      logging.warning('gae_ts_mon error: Key "metrics" must be in body.')
      logging.warning('Request body: %s', body)
      return

    for metric_measurement in body.get('metrics', []):
      name = metric_measurement['MetricInfo']['Name']
      metric = self._metrics.get(name, None)

      if not metric:
        self.response.set_status(400)
        self.response.write('Metric "%s" is not defined.' % name)
        logging.warning(
            'gae_ts_mon error: Metric "%s" is not defined.', name)
        return

      for cell in metric_measurement.get('Cells', []):
        fields = cell.get('fields', {})
        value = cell.get('value')

        metric_field_keys = set(fs.name for fs in metric.field_spec)
        if set(fields.keys()) != metric_field_keys:
          self.response.set_status(400)
          self.response.write('Supplied fields do not match metric "%s".' % name)
          logging.warning(
              'gae_ts_mon error: Supplied fields do not match metric "%s".',
              name)
          logging.warning('Supplied fields keys: %s', fields.keys())
          logging.warning('Metric fields keys: %s', metric_field_keys)
          return

        start_time = cell.get('start_time')
        if metric.is_cumulative() and not start_time:
          self.response.set_status(400)
          self.response.write('Cumulative metrics must have start_time.')
          logging.warning(
              'gae_ts_mon error: Cumulative metrics must have start_time.')
          logging.warning('Metric name: %s', name)
          return

        if metric.is_cumulative() and not self._start_time_is_valid(start_time):
          self.response.set_status(400)
          self.response.write('Invalid start_time: %s.' % start_time)
          logging.warning(
              'gae_ts_mon error: Invalid start_time: %s.', start_time)
          return

        # Convert distribution metric values into Distribution classes.
        if (isinstance(metric, (metrics.CumulativeDistributionMetric,
                                metrics.NonCumulativeDistributionMetric))):
          if not isinstance(value, dict):
            self.response.set_status(400)
            self.response.write('Distribution metric values must be a dict.')
            logging.warning(
                'gae_ts_mon error: Distribution metric values must be a dict.')
            logging.warning('Metric value: %s', value)
            return
          dist_value = distribution.Distribution(bucketer=metric.bucketer)
          dist_value.sum = value.get('sum', 0)
          dist_value.count = value.get('count', 0)
          dist_value.buckets.update(value.get('buckets', {}))
          metric.set(dist_value, fields=fields)
        else:
          metric.set(value, fields=fields)

        if metric.is_cumulative():
          metric.dangerously_set_start_time(start_time)

    self.response.set_status(201)
    self.response.write('Ok.')

  def xsrf_is_valid(self, _body):
    """Takes a request body and returns whether the included XSRF token
    is valid.

    This method must be implemented by a subclass.
    """
    raise NotImplementedError('xsrf_is_valid must be implemented in a subclass.')

  def time_fn(self):
    """Defaults to time.time. Can be overridden for testing."""
    return time.time()

  def _start_time_is_valid(self, start_time):
    """Validates that a start_time is not in the future and not
    more than a month in the past.
    """
    now = self.time_fn()
    if start_time > now:
      return False

    one_month_seconds = 60 * 60 * 24 * 30
    one_month_ago = now - one_month_seconds
    if start_time < one_month_ago:
      return False

    return True


def report_memory(application):
  """Wraps an app so handlers log when memory usage increased by at least 0.5MB
  after the handler completed.
  """
  if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    # Otherwise this fails with:
    # AssertionError: No api proxy found for service "system"
    return # pragma: no cover
  min_delta = 0.5
  old_dispatcher = application.router.dispatch
  def dispatch_and_report(*args, **kwargs):
    before = apiruntime.runtime.memory_usage().current()
    try:
      return old_dispatcher(*args, **kwargs)
    finally:
      after = apiruntime.runtime.memory_usage().current()
      if after >= before + min_delta: # pragma: no cover
        logging.debug(
            'Memory usage: %.1f -> %.1f MB; delta: %.1f MB',
            before, after, after - before)
  application.router.dispatch = dispatch_and_report


def create_app():
  ts_mon_app = webapp2.WSGIApplication([
      (r'/internal/cron/ts_mon/send', SendHandler),
  ])
  report_memory(ts_mon_app)
  return ts_mon_app


app = create_app()
