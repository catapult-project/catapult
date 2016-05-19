# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import math
import unittest

import mock
import webapp2
import webtest

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from dashboard import add_point
from dashboard import add_point_queue
from dashboard import layered_cache
from dashboard import testing_common
from dashboard import units_to_direction
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.models import sheriff

# TODO(qyearsley): Shorten this module.
# See https://github.com/catapult-project/catapult/issues/1917
# pylint: disable=too-many-lines

# A limit to the number of entities that can be fetched. This is just an
# safe-guard to prevent possibly fetching too many entities.
_FETCH_LIMIT = 100

# Sample point which contains all of the required fields.
_SAMPLE_POINT = {
    'master': 'ChromiumPerf',
    'bot': 'win7',
    'test': 'my_test_suite/my_test',
    'revision': 12345,
    'value': 22.4,
}

# Sample Dashboard JSON v1.0 point.
_SAMPLE_DASHBOARD_JSON = {
    'master': 'ChromiumPerf',
    'bot': 'win7',
    'point_id': '12345',
    'test_suite_name': 'my_test_suite',
    'supplemental': {
        'os': 'mavericks',
        'gpu_oem': 'intel'
    },
    'versions': {
        'chrome': '12.3.45.6',
        'blink': '234567'
    },
    'chart_data': {
        'benchmark_name': 'my_benchmark',
        'benchmark_description': 'foo',
        'format_version': '1.0',
        'charts': {
            'my_test': {
                'summary': {
                    'type': 'scalar',
                    'name': 'my_test',
                    'units': 'ms',
                    'value': 22.4,
                }
            }
        }
    }
}

# Sample Dashboard JSON v1.0 point with trace data.
_SAMPLE_DASHBOARD_JSON_WITH_TRACE = {
    'master': 'ChromiumPerf',
    'bot': 'win7',
    'point_id': '12345',
    'test_suite_name': 'my_test_suite',
    'supplemental': {
        'os': 'mavericks',
        'gpu_oem': 'intel'
    },
    'versions': {
        'chrome': '12.3.45.6',
        'blink': '234567'
    },
    'chart_data': {
        'benchmark_name': 'my_benchmark',
        'benchmark_description': 'foo',
        'format_version': '1.0',
        'charts': {
            'my_test': {
                'trace1': {
                    'type': 'scalar',
                    'name': 'my_test1',
                    'units': 'ms',
                    'value': 22.4,
                },
                'trace2': {
                    'type': 'scalar',
                    'name': 'my_test2',
                    'units': 'ms',
                    'value': 33.2,
                }
            },
            'trace': {
                'trace1': {
                    'name': 'trace',
                    'type': 'trace',
                    # No cloud_url, should be handled properly
                },
                'trace2': {
                    'name': 'trace',
                    'cloud_url': 'https:\\/\\/console.developer.google.com\\/m',
                    'type': 'trace',
                }
            }
        }
    }
}

# Units to direction to use in the tests below.
_UNITS_TO_DIRECTION_DICT = {
    'ms': {'improvement_direction': 'down'},
    'fps': {'improvement_direction': 'up'},
}

# Sample IP addresses to use in the tests below.
_WHITELISTED_IP = '123.45.67.89'


class AddPointTest(testing_common.TestCase):

  def setUp(self):
    super(AddPointTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/add_point', add_point.AddPointHandler),
        ('/add_point_queue', add_point_queue.AddPointQueueHandler)])
    self.testapp = webtest.TestApp(app)
    units_to_direction.UpdateFromJson(_UNITS_TO_DIRECTION_DICT)
    # Set up the default whitelisted IP used in the tests below.
    # Note: The behavior of responses from whitelisted and unwhitelisted IPs
    # is tested in post_data_handler_test.py.
    testing_common.SetIpWhitelist([_WHITELISTED_IP])
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPost_MonitoredRow_CorrectlyAdded(self):
    """Tests that adding a chart causes the correct row to be added."""
    sheriff.Sheriff(
        id='X', patterns=['ChromiumPerf/win7/my_test_suite/*']).put()
    data_param = json.dumps(_SAMPLE_DASHBOARD_JSON)
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    rows = graph_data.Row.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(1, len(rows))
    self.assertEqual(12345, rows[0].revision)
    self.assertEqual(22.4, rows[0].value)
    self.assertEqual(0, rows[0].error)
    self.assertEqual('12.3.45.6', rows[0].r_chrome)
    self.assertEqual('234567', rows[0].r_blink)
    self.assertEqual('mavericks', rows[0].a_os)
    self.assertEqual('intel', rows[0].a_gpu_oem)
    test_suite = ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'win7', 'Test', 'my_test_suite').get()
    self.assertEqual('foo', test_suite.description)

  def testPost_UnmonitoredRow_NotAdded(self):
    """Tests that adding a chart causes the correct row to be added."""
    data_param = json.dumps(_SAMPLE_DASHBOARD_JSON)
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    rows = graph_data.Row.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(0, len(rows))

  def testPost_TestPathTooLong_PointRejected(self):
    """Tests that an error is returned when the test path would be too long."""
    point = copy.deepcopy(_SAMPLE_POINT)
    point['test'] = 'long_test/%s' % ('x' * 490)
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(0, len(tests))

  def testPost_TrailingSlash_Ignored(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    point['test'] = 'mach_ports_parent/mach_ports/'
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    self.assertEqual('mach_ports_parent', tests[0].key.id())
    self.assertEqual('mach_ports', tests[1].key.id())
    self.assertEqual('mach_ports_parent', tests[1].parent_test.id())

  def testPost_LeadingSlash_Ignored(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    point['test'] = '/boot_time/pre_plugin_time'
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    self.assertEqual('boot_time', tests[0].key.id())
    self.assertEqual('pre_plugin_time', tests[1].key.id())
    self.assertEqual('boot_time', tests[1].parent_test.id())

  def testPost_BadJson_DataRejected(self):
    """Tests that an error is returned when the given data is not valid JSON."""
    self.testapp.post(
        '/add_point', {'data': "This isn't JSON"}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_BadGraphName_DataRejected(self):
    """Tests that an error is returned when the test name has too many parts."""
    point = copy.deepcopy(_SAMPLE_POINT)
    point['test'] = 'a/b/c/d/e/f/g/h/i/j/k'
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_TestNameHasDoubleUnderscores_Rejected(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    point['test'] = 'my_test_suite/__my_test__'
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  @mock.patch('logging.error')
  @mock.patch.object(graph_data.Master, 'get_by_id')
  def testPost_BadRequestError_ErrorLogged(
      self, mock_get_by_id, mock_logging_error):
    """Tests that error is logged if a datastore BadRequestError happens."""
    mock_get_by_id.side_effect = datastore_errors.BadRequestError
    self.testapp.post(
        '/add_point', {'data': json.dumps([_SAMPLE_POINT])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    self.assertEqual(1, len(mock_logging_error.mock_calls))

  def testPost_IncompleteData_DataRejected(self):
    """Tests that an error is returned when the given columns are invalid."""
    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'foo/bar/baz',
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_NoRevisionAndNoVersionNums_Rejected(self):
    """Asserts post fails when both revision and version numbers are missing."""
    data_param = json.dumps([
        {
            'master': 'CrosPerf',
            'bot': 'lumpy',
            'test': 'mach_ports/mach_ports/',
            'value': '231.666666667',
            'error': '2.28521820013',
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_InvalidRevision_Rejected(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    point['revision'] = 'I am not a valid revision number!'
    response = self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.assertIn(
        'Bad value for "revision", should be numerical.\n', response.body)

  def testPost_NewTest_AnomalyConfigPropertyIsAdded(self):
    """Tests that AnomalyConfig keys are added to Tests upon creation.

    Like with sheriffs, AnomalyConfig keys are to Test when the Test is put
    if the Test matches the pattern of the AnomalyConfig.
    """
    anomaly_config1 = anomaly_config.AnomalyConfig(
        id='anomaly_config1', config='',
        patterns=['ChromiumPerf/*/dromaeo/jslib']).put()
    anomaly_config2 = anomaly_config.AnomalyConfig(
        id='anomaly_config2', config='',
        patterns=['*/*image_benchmark/*', '*/*/scrolling_benchmark/*']).put()

    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'scrolling_benchmark/mean_frame_time',
            'revision': 123456,
            'value': 700,
        },
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'dromaeo/jslib',
            'revision': 123445,
            'value': 200,
        },
        {
            'master': 'ChromiumWebkit',
            'bot': 'win7',
            'test': 'dromaeo/jslib',
            'revision': 12345,
            'value': 205.3,
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    anomaly_config1_test = ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'win7',
        'Test', 'dromaeo', 'Test', 'jslib').get()
    self.assertEqual(
        anomaly_config1, anomaly_config1_test.overridden_anomaly_config)

    anomaly_config2_test = ndb.Key(
        'Master', 'ChromiumPerf', 'Bot', 'win7', 'Test',
        'scrolling_benchmark', 'Test', 'mean_frame_time').get()
    self.assertEqual(
        anomaly_config2, anomaly_config2_test.overridden_anomaly_config)

    no_config_test = ndb.Key(
        'Master', 'ChromiumWebkit', 'Bot', 'win7',
        'Test', 'dromaeo', 'Test', 'jslib').get()
    self.assertIsNone(no_config_test.overridden_anomaly_config)

  def testPost_NewTest_AddsUnits(self):
    """Tests that units and improvement direction are added for new Tests."""
    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'scrolling_benchmark/mean_frame_time',
            'revision': 123456,
            'value': 700,
            'units': 'ms',
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    self.assertEqual('scrolling_benchmark', tests[0].key.string_id())
    self.assertIsNone(tests[0].units)
    self.assertEqual(anomaly.UNKNOWN, tests[0].improvement_direction)
    self.assertEqual('mean_frame_time', tests[1].key.string_id())
    self.assertEqual('ms', tests[1].units)
    self.assertEqual(anomaly.DOWN, tests[1].improvement_direction)

  def testPost_NewPointWithNewUnits_TestUnitsAreUpdated(self):
    parent = graph_data.Master(id='ChromiumPerf').put()
    parent = graph_data.Bot(id='win7', parent=parent).put()
    parent = graph_data.Test(id='scrolling_benchmark', parent=parent).put()
    graph_data.Test(
        id='mean_frame_time', parent=parent, units='ms',
        improvement_direction=anomaly.DOWN).put()

    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'scrolling_benchmark/mean_frame_time',
            'revision': 123456,
            'value': 700,
            'units': 'fps',
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    self.assertEqual('scrolling_benchmark', tests[0].key.string_id())
    self.assertIsNone(tests[0].units)
    self.assertEqual(anomaly.UNKNOWN, tests[0].improvement_direction)
    self.assertEqual('mean_frame_time', tests[1].key.string_id())
    self.assertEqual('fps', tests[1].units)
    self.assertEqual(anomaly.UP, tests[1].improvement_direction)

  def testPost_NewPoint_UpdatesImprovementDirection(self):
    """Tests that adding a point updates units for an existing Test."""
    parent = graph_data.Master(id='ChromiumPerf').put()
    parent = graph_data.Bot(id='win7', parent=parent).put()
    parent = graph_data.Test(id='scrolling_benchmark', parent=parent).put()
    frame_time_key = graph_data.Test(
        id='frame_time', parent=parent, units='ms',
        improvement_direction=anomaly.DOWN).put()
    # Before sending the new data point, the improvement direction is down.
    test = frame_time_key.get()
    self.assertEqual(anomaly.DOWN, test.improvement_direction)
    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'scrolling_benchmark/frame_time',
            'revision': 123456,
            'value': 700,
            'units': 'ms',
            'higher_is_better': True,
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    # After sending the new data which explicitly specifies an improvement
    # direction, the improvement direction is changed even though the units
    # (ms) usually indicates an improvement direction of down.
    test = frame_time_key.get()
    self.assertEqual(anomaly.UP, test.improvement_direction)

  def testPost_DirectionUpdatesWithUnitMap(self):
    """Tests that adding a point updates units for an existing Test."""
    parent = graph_data.Master(id='ChromiumPerf').put()
    parent = graph_data.Bot(id='win7', parent=parent).put()
    parent = graph_data.Test(id='scrolling_benchmark', parent=parent).put()
    graph_data.Test(
        id='mean_frame_time',
        parent=parent,
        units='ms',
        improvement_direction=anomaly.UNKNOWN).put()
    point = {
        'master': 'ChromiumPerf',
        'bot': 'win7',
        'test': 'scrolling_benchmark/mean_frame_time',
        'revision': 123456,
        'value': 700,
        'units': 'ms',
    }
    self.testapp.post('/add_point',
                      {'data': json.dumps([point])},
                      extra_environ={'REMOTE_ADDR': '123.45.67.89'})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    self.assertEqual('scrolling_benchmark', tests[0].key.string_id())
    self.assertIsNone(tests[0].units)
    self.assertEqual(anomaly.UNKNOWN, tests[0].improvement_direction)
    self.assertEqual('mean_frame_time', tests[1].key.string_id())
    self.assertEqual('ms', tests[1].units)
    self.assertEqual(anomaly.DOWN, tests[1].improvement_direction)

  def testPost_AddNewPointToDeprecatedTest_ResetsDeprecated(self):
    """Tests that adding a point sets the test to be non-deprecated."""
    parent = graph_data.Master(id='ChromiumPerf').put()
    parent = graph_data.Bot(id='win7', parent=parent).put()
    suite = graph_data.Test(
        id='scrolling_benchmark', parent=parent, deprecated=True).put()
    graph_data.Test(id='mean_frame_time', parent=suite, deprecated=True).put()

    point = {
        'master': 'ChromiumPerf',
        'bot': 'win7',
        'test': 'scrolling_benchmark/mean_frame_time',
        'revision': 123456,
        'value': 700,
    }
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    tests = graph_data.Test.query().fetch(limit=_FETCH_LIMIT)
    self.assertEqual(2, len(tests))
    # Note that the parent test is also marked as non-deprecated.
    self.assertEqual('scrolling_benchmark', tests[0].key.string_id())
    self.assertFalse(tests[0].deprecated)
    self.assertEqual('mean_frame_time', tests[1].key.string_id())
    self.assertFalse(tests[1].deprecated)

  def testPost_NewSuite_CachedSubTestsDeleted(self):
    """Tests that cached test lists are cleared as new test suites are added."""
    # Set the cached test lists. Note that no actual Test entities are added
    # here, so when a new point is added, it will still count as a new Test.
    layered_cache.Set(
        graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
            'ChromiumPerf', 'win7', 'scrolling_benchmark'),
        {'foo': 'bar'})
    layered_cache.Set(
        graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
            'ChromiumPerf', 'mac', 'scrolling_benchmark'),
        {'foo': 'bar'})
    data_param = json.dumps([
        {
            'master': 'ChromiumPerf',
            'bot': 'win7',
            'test': 'scrolling_benchmark/mean_frame_time',
            'revision': 123456,
            'value': 700,
        }
    ])
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    # Subtests for ChromiumPerf/win7/scrolling_benchmark should be cleared.
    self.assertIsNone(layered_cache.Get(
        graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
            'ChromiumPerf', 'win7', 'scrolling_benchmark')))
    # Subtests for another bot should NOT be cleared.
    self.assertEqual({'foo': 'bar'}, layered_cache.Get(
        graph_data.LIST_TESTS_SUBTEST_CACHE_KEY % (
            'ChromiumPerf', 'mac', 'scrolling_benchmark')))

  def testParseColumns(self):
    """Tests that the GetAndValidateRowProperties method handles valid data."""
    expected = {
        'value': 444.55,
        'error': 12.3,
        'r_webkit': '12345',
        'r_skia': '43210',
        'a_note': 'hello',
        'd_run_1': 444.66,
        'd_run_2': 444.44,
    }
    actual = add_point.GetAndValidateRowProperties(
        {
            'revision': 12345,
            'value': 444.55,
            'error': 12.3,
            'supplemental_columns': {
                'r_webkit': 12345,
                'r_skia': 43210,
                'a_note': 'hello',
                'd_run_1': 444.66,
                'd_run_2': 444.44,
            },
        }
    )
    self.assertEqual(expected, actual)

  def testPost_NoValue_Rejected(self):
    """Tests the error returned when no "value" is given."""
    point = copy.deepcopy(_SAMPLE_POINT)
    del point['value']
    response = self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.assertIn('No "value" given.\n', response.body)
    self.assertIsNone(graph_data.Row.query().get())

  def testPost_WithBadValue_Rejected(self):
    """Tests the error returned when an invalid "value" is given."""
    point = copy.deepcopy(_SAMPLE_POINT)
    point['value'] = 'hello'
    response = self.testapp.post(
        '/add_point', {'data': json.dumps([point])}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    self.assertIn(
        'Bad value for "value", should be numerical.\n', response.body)
    self.assertIsNone(graph_data.Row.query().get())

  def testPost_BadSupplementalColumnName_ColumnDropped(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    point['supplemental_columns'] = {'q_foo': 'bar'}

    self.testapp.post(
        '/add_point', {'data': json.dumps([point])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    # Supplemental columns with undefined prefixes should be dropped.
    row = graph_data.Row.query().get()
    self.assertFalse(hasattr(row, 'q_foo'))

  def testPost_LongSupplementalColumnName_ColumnDropped(self):
    point = copy.deepcopy(_SAMPLE_POINT)
    key = 'a_' + ('a' * add_point._MAX_COLUMN_NAME_LENGTH)
    point['supplemental_columns'] = {
        key: '1234',
    }
    self.testapp.post(
        '/add_point', {'data': json.dumps([point])},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)

    # Supplemental columns with super long names should be dropped.
    row = graph_data.Row.query().get()
    self.assertFalse(hasattr(row, key))

  def testPost_NoTestSuiteName_BenchmarkNameUsed(self):
    sample = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    del sample['test_suite_name']
    data_param = json.dumps(sample)
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    self.assertIsNone(utils.TestKey('ChromiumPerf/win7/my_test_suite').get())
    self.assertIsNotNone(utils.TestKey('ChromiumPerf/win7/my_benchmark').get())

  def testPost_TestSuiteNameIsNone_BenchmarkNameUsed(self):
    sample = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    sample['test_suite_name'] = None
    data_param = json.dumps(sample)
    self.testapp.post(
        '/add_point', {'data': data_param},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    self.ExecuteTaskQueueTasks('/add_point_queue', add_point._TASK_QUEUE_NAME)
    self.assertIsNone(utils.TestKey('ChromiumPerf/win7/my_test_suite').get())
    self.assertIsNotNone(utils.TestKey('ChromiumPerf/win7/my_benchmark').get())

  def testPost_FormatV1_BadMaster_Rejected(self):
    """Tests that attempting to post with no master name will error."""
    chart = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    del chart['master']
    self.testapp.post(
        '/add_point', {'data': json.dumps(chart)}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_FormatV1_BadBot_Rejected(self):
    """Tests that attempting to post with no bot name will error."""
    chart = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    del chart['bot']
    self.testapp.post(
        '/add_point', {'data': json.dumps(chart)}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_FormatV1_BadPointId_Rejected(self):
    """Tests that attempting to post a chart no point id will error."""
    chart = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    del chart['point_id']
    self.testapp.post(
        '/add_point', {'data': json.dumps(chart)}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_GarbageDict_Rejected(self):
    """Tests that posting an ill-formatted dict will error."""
    chart = {'foo': 'garbage'}
    self.testapp.post(
        '/add_point', {'data': json.dumps(chart)}, status=400,
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})

  def testPost_FormatV1_EmptyCharts_NothingAdded(self):
    chart = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    chart['chart_data']['charts'] = {}
    self.testapp.post(
        '/add_point', {'data': json.dumps(chart)},
        extra_environ={'REMOTE_ADDR': _WHITELISTED_IP})
    # Status is OK, but no rows are added.
    self.assertIsNone(graph_data.Row.query().get())


class FlattenTraceTest(testing_common.TestCase):

  def testDashboardJsonToRawRows_WithIsRef(self):
    """Tests that rows from a chart from a ref build have the correct name."""
    chart = copy.deepcopy(_SAMPLE_DASHBOARD_JSON)
    chart['is_ref'] = True
    rows = add_point._DashboardJsonToRawRows(chart)
    self.assertEqual('my_test_suite/my_test/ref', rows[0]['test'])

  @staticmethod
  def _SampleTrace():
    return {
        'name': 'bar.baz',
        'units': 'meters',
        'type': 'scalar',
        'value': 42,
    }

  def testFlattenTrace_PreservesUnits(self):
    """Tests that _FlattenTrace preserves the units property."""
    trace = self._SampleTrace()
    trace.update({'units': 'ms'})
    row = add_point._FlattenTrace('foo', 'bar', 'bar', trace)
    self.assertEqual(row['units'], 'ms')

  def testFlattenTrace_CoreTraceName(self):
    """Tests that chartname.summary will be flattened to chartname."""
    trace = self._SampleTrace()
    trace.update({'name': 'summary'})
    row = add_point._FlattenTrace('foo', 'bar', 'summary', trace)
    self.assertEqual(row['test'], 'foo/bar')

  def testFlattenTrace_NonSummaryTraceName_SetCorrectly(self):
    """Tests that chart.trace will be flattened to chart/trace."""
    trace = self._SampleTrace()
    trace.update({'name': 'bar.baz'})
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertEqual(row['test'], 'foo/bar/baz')

  def testFlattenTrace_ImprovementDirectionCannotBeNone(self):
    """Tests that an improvement_direction must not be None if passed."""
    trace = self._SampleTrace()
    trace.update({'improvement_direction': None})
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'summary', trace)

  def testFlattenTrace_AddsImprovementDirectionIfPresent(self):
    """Tests that improvement_direction will be respected if present."""
    trace = self._SampleTrace()
    trace.update({'improvement_direction': 'up'})
    row = add_point._FlattenTrace('foo', 'bar', 'summary', trace)
    self.assertTrue(row['higher_is_better'])

  def testFlattenTrace_DoesNotAddImprovementDirectionIfAbsent(self):
    """Tests that no higher_is_better is added if no improvement_direction."""
    row = add_point._FlattenTrace('foo', 'bar', 'summary', self._SampleTrace())
    self.assertNotIn('higher_is_better', row)

  def testFlattenTrace_RejectsBadImprovementDirection(self):
    """Tests that passing a bad improvement_direction will cause an error."""
    trace = self._SampleTrace()
    trace.update({'improvement_direction': 'foo'})
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'summary', trace)

  def testFlattenTrace_ScalarValue(self):
    """Tests that scalars are flattened to 0-error values."""
    row = add_point._FlattenTrace('foo', 'bar', 'baz', self._SampleTrace())
    self.assertEqual(row['value'], 42)
    self.assertEqual(row['error'], 0)

  def testFlattenTrace_ScalarNoneValue(self):
    """Tests that scalar NoneValue is flattened to NaN."""
    trace = self._SampleTrace()
    trace.update({'value': None, 'none_value_reason': 'reason'})
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertTrue(math.isnan(row['value']))
    self.assertEqual(row['error'], 0)

  def testFlattenTrace_ScalarLongValue(self):
    """Tests that scalar values can be longs."""
    trace = self._SampleTrace()
    trace.update({'value': 1000000000L})
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertEqual(row['value'], 1000000000L)
    self.assertEqual(row['error'], 0)

  def testFlattenTrace_InvalidScalarValue_RaisesError(self):
    """Tests that scalar NoneValue is flattened to NaN."""
    trace = self._SampleTrace()
    trace.update({'value': [42, 43, 44]})
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'baz', trace)

  def testFlattenTrace_ListValue(self):
    """Tests that lists are properly flattened to avg/stddev."""
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'values': [5, 10, 25, 10, 15],
    })
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertAlmostEqual(row['value'], 13)
    self.assertAlmostEqual(row['error'], 6.78232998)

  def testFlattenTrace_ListValue_WithLongs(self):
    """Tests that lists of scalars can include longs."""
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'values': [1000000000L, 2000000000L],
    })
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertAlmostEqual(row['value'], 1500000000L)
    self.assertAlmostEqual(row['error'], 500000000L)

  def testFlattenTrace_ListValueWithStd(self):
    """Tests that lists with reported std use std as error."""
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'values': [5, 10, 25, 10, 15],
        'std': 100,
    })
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertNotAlmostEqual(row['error'], 6.78232998)
    self.assertEqual(row['error'], 100)

  def testFlattenTrace_ListNoneValue(self):
    """Tests that LoS NoneValue is flattened to NaN."""
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'value': [None],
        'none_value_reason': 'Reason for null value'
    })
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertTrue(math.isnan(row['value']))
    self.assertTrue(math.isnan(row['error']))

  def testFlattenTrace_ListNoneValueNoReason_RaisesError(self):
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'value': [None],
    })
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'baz', trace)

  def testFlattenTrace_ListValueNotAList_RaisesError(self):
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'values': 42,
    })
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'baz', trace)

  def testFlattenTrace_ListContainsString_RaisesError(self):
    trace = self._SampleTrace()
    trace.update({
        'type': 'list_of_scalar_values',
        'values': ['-343', 123],
    })
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'baz', trace)

  def testFlattenTrace_HistogramValue(self):
    """Tests that histograms are yield geommean/stddev as value/error."""
    trace = self._SampleTrace()
    trace.update({
        'type': 'histogram',
        'buckets': [{'low': 1, 'high': 5, 'count': 3},
                    {'low': 4, 'high': 6, 'count': 4}]
    })
    row = add_point._FlattenTrace('foo', 'bar', 'baz', trace)
    self.assertAlmostEqual(row['value'], 4.01690877)
    self.assertAlmostEqual(row['error'], 0.99772482)

  def testFlattenTrace_RespectsIsRefForSameTraceName(self):
    """Tests whether a ref trace that is a chart has the /ref suffix."""
    row = add_point._FlattenTrace(
        'foo', 'bar', 'summary', self._SampleTrace(), is_ref=True)
    self.assertEqual(row['test'], 'foo/bar/ref')

  def testFlattenTrace_RespectsIsRefForDifferentTraceName(self):
    """Tests whether a ref trace that is not a chart has the _ref suffix."""
    row = add_point._FlattenTrace(
        'foo', 'bar', 'baz', self._SampleTrace(), is_ref=True)
    self.assertEqual(row['test'], 'foo/bar/baz_ref')

  def testFlattenTrace_InvalidTraceType(self):
    """Tests whether a ref trace that is not a chart has the _ref suffix."""
    trace = self._SampleTrace()
    trace.update({'type': 'foo'})
    with self.assertRaises(add_point.BadRequestError):
      add_point._FlattenTrace('foo', 'bar', 'baz', trace)

  def testFlattenTrace_SanitizesTraceName(self):
    """Tests whether a trace name with special characters is sanitized."""
    trace = self._SampleTrace()
    trace.update({'page': 'http://example.com'})
    row = add_point._FlattenTrace(
        'foo', 'bar', 'http://example.com', trace)
    self.assertEqual(row['test'], 'foo/bar/http___example.com')

  def testFlattenTrace_FlattensInteractionRecordLabelToFivePartName(self):
    """Tests whether a TIR label will appear between chart and trace name."""
    trace = self._SampleTrace()
    trace.update({
        'name': 'bar',
        'page': 'https://abc.xyz/',
        'tir_label': 'baz'
    })
    row = add_point._FlattenTrace('foo', 'baz@@bar', 'https://abc.xyz/', trace)
    self.assertEqual(row['test'], 'foo/bar/baz/https___abc.xyz_')


if __name__ == '__main__':
  unittest.main()
