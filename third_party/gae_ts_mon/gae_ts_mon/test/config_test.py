# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import datetime
import functools
import os
import time
import unittest

import endpoints
import gae_ts_mon
import mock
import webapp2

from infra_libs.ts_mon import config
from infra_libs.ts_mon import shared
from infra_libs.ts_mon.common import http_metrics
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common import targets
from protorpc import message_types
from protorpc import remote
from testing_utils import testing


class InitializeTest(testing.AppengineTestCase):
  def setUp(self):
    super(InitializeTest, self).setUp()

    config.reset_for_unittest()
    target = targets.TaskTarget('test_service', 'test_job',
                                'test_region', 'test_host')
    self.mock_state = interface.State(target=target)
    self.mock_state.metrics = copy.copy(interface.state.metrics)
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.common.monitors.HttpsMonitor',
               autospec=True).start()

  def tearDown(self):
    config.reset_for_unittest()
    mock.patch.stopall()
    super(InitializeTest, self).tearDown()

  def test_sets_target(self):
    config.initialize(is_local_unittest=False)

    self.assertEqual('testbed-test', self.mock_state.target.service_name)
    self.assertEqual('default', self.mock_state.target.job_name)
    self.assertEqual('appengine', self.mock_state.target.region)
    self.assertEqual('testbed', self.mock_state.target.hostname)

  def test_sets_monitor(self):
    os.environ['SERVER_SOFTWARE'] = 'Production'  # != 'Development'

    config.initialize(is_local_unittest=False)

    self.assertEquals(1, monitors.HttpsMonitor.call_count)

  def test_sets_monitor_dev(self):
    config.initialize(is_local_unittest=False)

    self.assertFalse(monitors.HttpsMonitor.called)
    self.assertIsInstance(self.mock_state.global_monitor, monitors.DebugMonitor)

  def test_instruments_app(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    self.assertEqual(1, http_metrics.server_response_status.get({
        'name': '^/$', 'status': 200, 'is_robot': False}))

  def test_instrument_app_with_enabled_fn(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    is_enabled_fn = mock.Mock()

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_enabled_fn=is_enabled_fn, is_local_unittest=False)
    app.get_response('/')
    self.assertIs(is_enabled_fn, interface.state.flush_enabled_fn)

  def test_instruments_app_only_once(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_reset_cumulative_metrics(self):
    gauge = gae_ts_mon.GaugeMetric('gauge', 'foo', None)
    counter = gae_ts_mon.CounterMetric('counter', 'foo', None)
    gauge.set(5)
    counter.increment()
    self.assertEqual(5, gauge.get())
    self.assertEqual(1, counter.get())

    config._reset_cumulative_metrics()
    self.assertEqual(5, gauge.get())
    self.assertIsNone(counter.get())

  def test_flush_metrics_no_task_num(self):
    # We are not assigned task_num yet; cannot send metrics.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    more_than_min_ago = datetime_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = shared.get_instance_entity()
    entity.task_num = -1
    interface.state.target.task_num = -1
    self.assertFalse(config.flush_metrics_if_needed(time_now))

  def test_flush_metrics_no_task_num_too_long(self):
    # We are not assigned task_num for too long; cannot send metrics.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    too_long_ago = datetime_now - datetime.timedelta(
        seconds=shared.INSTANCE_EXPECTED_TO_HAVE_TASK_NUM_SEC+1)
    interface.state.last_flushed = too_long_ago
    entity = shared.get_instance_entity()
    entity.task_num = -1
    entity.last_updated = too_long_ago
    interface.state.target.task_num = -1
    self.assertFalse(config.flush_metrics_if_needed(time_now))

  def test_flush_metrics_purged(self):
    # We lost our task_num; cannot send metrics.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    more_than_min_ago = datetime_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = shared.get_instance_entity()
    entity.task_num = -1
    interface.state.target.task_num = 2
    self.assertFalse(config.flush_metrics_if_needed(time_now))

  def test_flush_metrics_too_early(self):
    # Too early to send metrics.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    less_than_min_ago = datetime_now - datetime.timedelta(seconds=59)
    interface.state.last_flushed = less_than_min_ago
    entity = shared.get_instance_entity()
    entity.task_num = 2
    self.assertFalse(config.flush_metrics_if_needed(time_now))

  @mock.patch('infra_libs.ts_mon.common.interface.flush', autospec=True)
  def test_flush_metrics_successfully(self, mock_flush):
    # We have task_num and due for sending metrics.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    more_than_min_ago = datetime_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = shared.get_instance_entity()
    entity.task_num = 2
    # Global metrics must be erased after flush.
    test_global_metric = gae_ts_mon.GaugeMetric('test', 'foo', None)
    test_global_metric.set(42)
    interface.register_global_metrics([test_global_metric])
    self.assertEqual(42, test_global_metric.get())
    self.assertTrue(config.flush_metrics_if_needed(time_now))
    self.assertEqual(None, test_global_metric.get())
    mock_flush.assert_called_once_with()

  @mock.patch('infra_libs.ts_mon.common.interface.flush', autospec=True)
  def test_flush_metrics_disabled(self, mock_flush):
    # We have task_num and due for sending metrics, but ts_mon is disabled.
    time_now = 10000
    datetime_now = datetime.datetime.utcfromtimestamp(time_now)
    more_than_min_ago = datetime_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    interface.state.flush_enabled_fn = lambda: False
    entity = shared.get_instance_entity()
    entity.task_num = 2
    self.assertFalse(config.flush_metrics_if_needed(time_now))
    self.assertEqual(0, mock_flush.call_count)

  @mock.patch('gae_ts_mon.config.flush_metrics_if_needed', autospec=True,
              return_value=True)
  def test_shutdown_hook_flushed(self, _mock_flush):
    time_now = 10000
    id = shared.get_instance_entity().key.id()
    with shared.instance_namespace_context():
      self.assertIsNotNone(shared.Instance.get_by_id(id))
    config._shutdown_hook(time_fn=lambda: time_now)
    with shared.instance_namespace_context():
      self.assertIsNone(shared.Instance.get_by_id(id))

  @mock.patch('gae_ts_mon.config.flush_metrics_if_needed', autospec=True,
              return_value=False)
  def test_shutdown_hook_not_flushed(self, _mock_flush):
    time_now = 10000
    id = shared.get_instance_entity().key.id()
    with shared.instance_namespace_context():
      self.assertIsNotNone(shared.Instance.get_by_id(id))
    config._shutdown_hook(time_fn=lambda: time_now)
    with shared.instance_namespace_context():
      self.assertIsNone(shared.Instance.get_by_id(id))

  def test_internal_callback(self):
    # Smoke test.
    config._internal_callback()


class InstrumentTest(testing.AppengineTestCase):
  def setUp(self):
    super(InstrumentTest, self).setUp()

    interface.reset_for_unittest()

    self.next_time = 42.0
    self.time_increment = 3.0

  def fake_time(self):
    ret = self.next_time
    self.next_time += self.time_increment
    return ret

  def test_success(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app, time_fn=self.fake_time)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertLessEqual(3000, http_metrics.server_durations.get(fields).sum)
    self.assertEqual(
        len('success!'), http_metrics.server_response_bytes.get(fields).sum)

  def test_abort(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.abort(417)

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 417, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_set_status(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.set_status(418)

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 418, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise ValueError

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 500, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_http_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise webapp2.exc.HTTPExpectationFailed()

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 417, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_return_response(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        ret = webapp2.Response()
        ret.set_status(418)
        return ret

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 418, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_robot(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        ret = webapp2.Response()
        ret.set_status(200)
        return ret

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/', user_agent='GoogleBot')

    fields = {'name': '^/$', 'status': 200, 'is_robot': True}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_missing_response_content_length(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        del self.response.headers['content-length']

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertIsNone(http_metrics.server_response_bytes.get(fields))

  def test_not_found(self):
    app = webapp2.WSGIApplication([])
    config.instrument_wsgi_application(app)

    app.get_response('/notfound')

    fields = {'name': '', 'status': 404, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_post(self):
    class Handler(webapp2.RequestHandler):
      def post(self):
        pass

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/', POST='foo')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertEqual(
        len('foo'), http_metrics.server_request_bytes.get(fields).sum)


class FakeTime(object):
  def __init__(self):
    self.timestamp_now = 1000.0

  def __call__(self):
    self.timestamp_now += 0.2
    return self.timestamp_now


@endpoints.api(name='testapi', version='v1')
class TestEndpoint(remote.Service):

  @gae_ts_mon.instrument_endpoint(time_fn=FakeTime())
  @endpoints.method(message_types.VoidMessage, message_types.VoidMessage,
                    name='method_good')
  def do_good(self, request):
    return request

  @gae_ts_mon.instrument_endpoint(time_fn=FakeTime())
  @endpoints.method(message_types.VoidMessage, message_types.VoidMessage,
                    name='method_bad')
  def do_bad(self, request):
    raise Exception

  @gae_ts_mon.instrument_endpoint(time_fn=FakeTime())
  @endpoints.method(message_types.VoidMessage, message_types.VoidMessage,
                    name='method_400')
  def do_400(self, request):
    raise endpoints.BadRequestException('Bad request')


class InstrumentEndpointTest(testing.EndpointsTestCase):
  api_service_cls = TestEndpoint

  def setUp(self):
    super(InstrumentEndpointTest, self).setUp()

    config.reset_for_unittest()
    target = targets.TaskTarget('test_service', 'test_job',
                                'test_region', 'test_host')
    self.mock_state = interface.State(target=target)
    self.mock_state.metrics = copy.copy(interface.state.metrics)
    self.endpoint_name = '/_ah/spi/TestEndpoint.%s'
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.common.monitors.HttpsMonitor',
               autospec=True).start()

  def tearDown(self):
    config.reset_for_unittest()
    mock.patch.stopall()
    super(InstrumentEndpointTest, self).tearDown()

  def test_good(self):
    self.call_api('do_good')
    fields = {'name': self.endpoint_name % 'method_good',
              'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertLessEqual(200, http_metrics.server_durations.get(fields).sum)

  def test_bad(self):
    with self.call_should_fail('500 Internal Server Error'):
      self.call_api('do_bad')
    fields = {'name': self.endpoint_name % 'method_bad',
              'status': 500, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertLessEqual(200, http_metrics.server_durations.get(fields).sum)

  def test_400(self):
    with self.call_should_fail('400 Bad Request'):
      self.call_api('do_400')
    fields = {'name': self.endpoint_name % 'method_400',
              'status': 400, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertLessEqual(200, http_metrics.server_durations.get(fields).sum)

  @mock.patch('gae_ts_mon.config.need_to_flush_metrics', autospec=True,
              return_value=False)
  def test_no_flush(self, _fake):
    # For branch coverage.
    self.call_api('do_good')
    fields = {'name': self.endpoint_name % 'method_good',
              'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertLessEqual(200, http_metrics.server_durations.get(fields).sum)


def view_func():
  pass  # pragma: no cover


class ViewClass(object):
  def view_method(self):
    pass  # pragma: no cover


def decorator(func):
  @functools.wraps(func)
  def wrapped():
    pass  # pragma: no cover
  return wrapped


@decorator
def decorated_view_func():
  pass  # pragma: no cover


class DjangoMiddlewareTest(testing.AppengineTestCase):

  def setUp(self):
    super(DjangoMiddlewareTest, self).setUp()

    interface.reset_for_unittest()
    self.m = config.DjangoMiddleware(time_fn=FakeTime())
    self.request = mock.Mock()
    self.request.body = 'x' * 42
    self.request.META = {'HTTP_USER_AGENT': 'useragent'}
    self.response = mock.Mock()
    self.response.status_code = 200
    self.response.content = 'x' * 43
    self.view_func = view_func

  def run_middleware(self):
    self.assertIsNone(self.m.process_view(self.request, self.view_func, [], {}))
    self.assertEquals(self.response,
        self.m.process_response(self.request, self.response))

  def test_good(self):
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))
    self.assertEquals(42, http_metrics.server_request_bytes.get(fields).sum)
    self.assertEquals(43, http_metrics.server_response_bytes.get(fields).sum)
    self.assertAlmostEquals(200, http_metrics.server_durations.get(fields).sum)

  def test_bad(self):
    self.response.status_code = 404
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 404, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))

  def test_robot(self):
    self.request.META['HTTP_USER_AGENT'] = 'GoogleBot'
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 200, 'is_robot': True}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))

  def test_view_method(self):
    self.view_func = ViewClass().view_method
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.ViewClass.view_method',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))

  def test_unbound_view_method(self):
    self.view_func = ViewClass.view_method
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.ViewClass.view_method',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))

  def test_decorated_view_func(self):
    self.view_func = decorated_view_func
    self.run_middleware()
    print self.request.ts_mon_state

    fields = {'name': 'gae_ts_mon.test.config_test.decorated_view_func',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))

  def test_response_without_request(self):
    del self.request.ts_mon_state
    # Doesn't raise.
    self.assertEquals(self.response,
        self.m.process_response(self.request, self.response))

  def test_missing_body(self):
    del self.request.body
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))
    self.assertEquals(0, http_metrics.server_request_bytes.get(fields).sum)
    self.assertEquals(43, http_metrics.server_response_bytes.get(fields).sum)
    self.assertEquals(1, http_metrics.server_response_bytes.get(fields).count)

  def test_missing_content(self):
    del self.response.content
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 200, 'is_robot': False}
    self.assertEquals(1, http_metrics.server_response_status.get(fields))
    self.assertEquals(42, http_metrics.server_request_bytes.get(fields).sum)
    self.assertEquals(0, http_metrics.server_response_bytes.get(fields).sum)
    self.assertEquals(1, http_metrics.server_response_bytes.get(fields).count)

  @mock.patch('gae_ts_mon.config.need_to_flush_metrics', autospec=True,
              return_value=False)
  def test_no_flush(self, _fake):
    # For branch coverage.
    self.run_middleware()

    fields = {'name': 'gae_ts_mon.test.config_test.view_func',
              'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
