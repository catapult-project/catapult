# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import datetime
import itertools
import logging
import mock
import unittest

from google.appengine.api import taskqueue

from dashboard.common import testing_common
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models import results2
from dashboard.pinpoint.models.change import change
from dashboard.pinpoint.models.change import commit
from dashboard.pinpoint.models.quest import read_value
from dashboard.pinpoint.models.quest import run_test
from dashboard.services import swarming
from dateutil.parser import isoparse
from tracing.value import histogram_set
from tracing.value import histogram as histogram_module

_TEST_START_TIME = datetime.datetime.fromtimestamp(1326244364)
_TEST_START_TIME_STR = _TEST_START_TIME.strftime('%Y-%m-%d %H:%M:%S.%f')

_ATTEMPT_DATA = {
    "executions": [{
        "result_arguments": {
            "isolate_server": "https://isolateserver.appspot.com",
            "isolate_hash": "e26a40a0d4",
        }
    }]
}

_JOB_NO_DIFFERENCES = {
    "state": [
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'next': 'same'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'next': 'same',
                'prev': 'same'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'next': 'same',
                'prev': 'same'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'prev': 'same'
            },
        },
    ],
    "quests": ["Test"],
}

_JOB_WITH_DIFFERENCES = {
    "state": [
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'next': 'same'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'prev': 'same',
                'next': 'different'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'prev': 'different',
                'next': 'different'
            },
        },
        {
            "attempts": [_ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'prev': 'different'
            },
        },
    ],
    "quests": ["Test"],
}

_JOB_MISSING_EXECUTIONS = {
    "state": [
        {
            "attempts": [_ATTEMPT_DATA, {
                "executions": []
            }],
            "change": {},
            "comparisons": {
                'next': 'same'
            },
        },
        {
            "attempts": [{
                "executions": []
            }, _ATTEMPT_DATA],
            "change": {},
            "comparisons": {
                'prev': 'same'
            },
        },
    ],
    "quests": ["Test"],
}

FakeBenchmarkArguments = collections.namedtuple(
    'FakeBenchmarkArguments', ['benchmark', 'story'])


@mock.patch.object(results2.cloudstorage, 'listbucket')
class GetCachedResults2Test(unittest.TestCase):

  def testGetCachedResults2_Cached_ReturnsResult(self, mock_cloudstorage):
    mock_cloudstorage.return_value = ['foo']

    job = _JobStub(_JOB_WITH_DIFFERENCES, '123', job_state.PERFORMANCE)
    url = results2.GetCachedResults2(job)

    self.assertEqual(
        'https://storage.cloud.google.com/results2-public/'
        '%s.html' % job.job_id, url)

  @mock.patch.object(results2, 'ScheduleResults2Generation', mock.MagicMock())
  def testGetCachedResults2_Uncached_Fails(self, mock_cloudstorage):
    mock_cloudstorage.return_value = []

    job = _JobStub(_JOB_WITH_DIFFERENCES, '123', job_state.PERFORMANCE)
    url = results2.GetCachedResults2(job)

    self.assertIsNone(url)


class ScheduleResults2Generation2Test(unittest.TestCase):

  @mock.patch.object(results2.taskqueue, 'add')
  def testScheduleResults2Generation2_FailedPreviously(self, mock_add):
    mock_add.side_effect = taskqueue.TombstonedTaskError

    job = _JobStub(_JOB_WITH_DIFFERENCES, '123', job_state.PERFORMANCE)
    result = results2.ScheduleResults2Generation(job)
    self.assertFalse(result)

  @mock.patch.object(results2.taskqueue, 'add')
  def testScheduleResults2Generation2_AlreadyRunning(self, mock_add):
    mock_add.side_effect = taskqueue.TaskAlreadyExistsError

    job = _JobStub(_JOB_WITH_DIFFERENCES, '123', job_state.PERFORMANCE)
    result = results2.ScheduleResults2Generation(job)
    self.assertTrue(result)


@mock.patch.object(
    results2, 'open', mock.mock_open(read_data='fake_viewer'), create=True)
class GenerateResults2Test(testing_common.TestCase):

  @mock.patch.object(
      results2, '_FetchHistograms',
      mock.MagicMock(return_value=[
          results2.HistogramData(None, ['a', 'b'])
      ]))
  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  def testPost_Renders(self, mock_render):
    job = _JobStub(None, '123', job_state.PERFORMANCE)
    results2.GenerateResults2(job)

    mock_render.assert_called_with([['a', 'b']],
                                   mock.ANY,
                                   reset_results=True,
                                   vulcanized_html='fake_viewer')

    results = results2.CachedResults2.query().fetch()
    self.assertEqual(1, len(results))

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  def testTypeDispatch_LegacyHistogramExecution(self, mock_json, mock_render):
    job = _JobStub(
        None, '123', job_state.PERFORMANCE,
        _JobStateFake({
            'f00c0de': [{
                'executions': [
                    read_value._ReadHistogramsJsonValueExecution(
                        'fake_filename', 'fake_metric', 'fake_grouping',
                        'fake_trace_or_story', 'avg', 'https://isolate_server',
                        'deadc0decafef00d')
                ]
            }]
        }))
    histograms = []

    def TraverseHistograms(hists, *unused_args, **unused_kw_args):
      for histogram in hists:
        histograms.append(histogram)

    mock_render.side_effect = TraverseHistograms
    histogram = histogram_module.Histogram('histogram', 'count')
    histogram.AddSample(0)
    histogram.AddSample(1)
    histogram.AddSample(2)
    expected_histogram_set = histogram_set.HistogramSet([histogram])
    mock_json.return_value = expected_histogram_set.AsDicts()
    results2.GenerateResults2(job)
    mock_render.assert_called_with(
        mock.ANY, mock.ANY, reset_results=True, vulcanized_html='fake_viewer')
    results = results2.CachedResults2.query().fetch()
    self.assertEqual(1, len(results))
    self.assertEqual(expected_histogram_set.AsDicts(), histograms)

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  def testTypeDispatch_LegacyGraphJsonExecution(self, mock_json, mock_render):
    job = _JobStub(
        None, '123', job_state.PERFORMANCE,
        _JobStateFake({
            'f00c0de': [{
                'executions': [
                    read_value._ReadGraphJsonValueExecution(
                        'fake_filename', 'fake_chart', 'fake_trace',
                        'https://isolate_server', 'deadc0decafef00d')
                ]
            }]
        }))
    histograms = []

    def TraverseHistograms(hists, *unused_args, **unused_kw_args):
      for histogram in hists:
        histograms.append(histogram)

    mock_render.side_effect = TraverseHistograms
    mock_json.return_value = {
        'fake_chart': {
            'traces': {
                'fake_trace': ['12345.6789', '0.0']
            }
        }
    }

    results2.GenerateResults2(job)
    mock_render.assert_called_with(
        mock.ANY, mock.ANY, reset_results=True, vulcanized_html='fake_viewer')
    results = results2.CachedResults2.query().fetch()
    self.assertEqual(1, len(results))
    # TODO(dberris): check more precisely the contents of the histograms.
    self.assertEqual([mock.ANY, mock.ANY], histograms)

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  def testTypeDispatch_ReadValueExecution(self, mock_json, mock_render):
    job = _JobStub(
        None, '123', job_state.PERFORMANCE,
        _JobStateFake({
            'f00c0de': [{
                'executions': [
                    read_value.ReadValueExecution(
                        'fake_filename', ['fake_filename'], 'fake_metric',
                        'fake_grouping_label', 'fake_trace_or_story', 'avg',
                        'fake_chart', 'https://isolate_server',
                        'deadc0decafef00d')
                ]
            }]
        }))
    histograms = []

    def TraverseHistograms(hists, *args, **kw_args):
      del args
      del kw_args
      for histogram in hists:
        histograms.append(histogram)

    mock_render.side_effect = TraverseHistograms
    histogram = histogram_module.Histogram('histogram', 'count')
    histogram.AddSample(0)
    histogram.AddSample(1)
    histogram.AddSample(2)
    expected_histogram_set = histogram_set.HistogramSet([histogram])
    mock_json.return_value = expected_histogram_set.AsDicts()
    results2.GenerateResults2(job)
    mock_render.assert_called_with(
        mock.ANY, mock.ANY, reset_results=True, vulcanized_html='fake_viewer')
    results = results2.CachedResults2.query().fetch()
    self.assertEqual(1, len(results))
    self.assertEqual(expected_histogram_set.AsDicts(), histograms)

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  def testTypeDispatch_ReadValueExecution_MultipleChanges(
      self, mock_json, mock_render):
    job = _JobStub(
        None, '123', job_state.PERFORMANCE,
        _JobStateFake({
            'f00c0de': [{
                'executions': [
                    read_value.ReadValueExecution(
                        'fake_filename', ['fake_filename'], 'fake_metric',
                        'fake_grouping_label', 'fake_trace_or_story', 'avg',
                        'fake_chart', 'https://isolate_server',
                        'deadc0decafef00d')
                ]
            }],
            'badc0de': [{
                'executions': [
                    read_value.ReadValueExecution(
                        'fake_filename', ['fake_filename'], 'fake_metric',
                        'fake_grouping_label', 'fake_trace_or_story', 'avg',
                        'fake_chart', 'https://isolate_server',
                        'deadc0decafef00d')
                ]
            }]
        }))
    histograms = []

    def TraverseHistograms(hists, *args, **kw_args):
      del args
      del kw_args
      for histogram in hists:
        histograms.append(histogram)

    mock_render.side_effect = TraverseHistograms
    histogram_a = histogram_module.Histogram('histogram', 'count')
    histogram_a.AddSample(0)
    histogram_a.AddSample(1)
    histogram_a.AddSample(2)
    expected_histogram_set_a = histogram_set.HistogramSet([histogram_a])
    histogram_b = histogram_module.Histogram('histogram', 'count')
    histogram_b.AddSample(0)
    histogram_b.AddSample(1)
    histogram_b.AddSample(2)
    expected_histogram_set_b = histogram_set.HistogramSet([histogram_b])

    mock_json.side_effect = (expected_histogram_set_a.AsDicts(),
                             expected_histogram_set_b.AsDicts())
    results2.GenerateResults2(job)
    mock_render.assert_called_with(
        mock.ANY, mock.ANY, reset_results=True, vulcanized_html='fake_viewer')
    results = results2.CachedResults2.query().fetch()
    self.assertEqual(1, len(results))
    self.assertEqual(
        expected_histogram_set_a.AsDicts() + expected_histogram_set_b.AsDicts(),
        histograms)

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2, '_InsertBQRows')
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  @mock.patch.object(swarming, 'Swarming')
  @mock.patch.object(commit.Commit, 'GetOrCacheCommitInfo')
  def testTypeDispatch_PushBQ_CH_CWV(self, mock_commit_info, mock_swarming,
                                     mock_json, mock_render, mock_bqinsert):
    expected_histogram_set = histogram_set.HistogramSet([
        _CreateHistogram('largestContentfulPaint', 42),
        _CreateHistogram('timeToFirstContentfulPaint', 11),
        _CreateHistogram('overallCumulativeLayoutShift', 22),
        _CreateHistogram('totalBlockingTime', 33),
        _CreateHistogram('someUselessMetric', 42)
    ])
    job = _SetupBQTest(mock_commit_info, mock_swarming, mock_render, mock_json,
                       expected_histogram_set)

    expected_rows = [{
        'job_start_time': _TEST_START_TIME_STR,
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'swarming_bot_id': 'fake_id',
                'os': ['os1', 'os2']
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0,
                'variant': 0
            },
            'checkout': {
                'repo': 'fakerepo',
                'git_hash': 'fakehashA',
                'commit_position': 437745,
                'commit_created': '2021-12-08 00:00:00.000000',
                'branch': 'refs/heads/main'
            }
        },
        'measures': {
            'core_web_vitals': {
                'timeToFirstContentfulPaint': 11.0,
                'totalBlockingTime': 33.0,
                'largestContentfulPaint': 42.0,
                'overallCumulativeLayoutShift': 22.0
            },
            'speedometer2': {}
        },
        'run_id': 'fake_job_id'
    }, {
        'job_start_time': _TEST_START_TIME_STR,
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'swarming_bot_id': 'fake_id',
                'os': ['os1', 'os2']
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0,
                'variant': 1
            },
            'checkout': {
                'patch_gerrit_revision': 'fake_patch_set',
                'commit_position': 437745,
                'commit_created': '2021-12-08 00:00:00.000000',
                'patch_gerrit_change': 'fake_patch_issue',
                'repo': 'fakeRepo',
                'branch': 'refs/heads/main',
                'git_hash': 'fakehashB'
            }
        },
        'measures': {
            'core_web_vitals': {
                'timeToFirstContentfulPaint': 11.0,
                'totalBlockingTime': 33.0,
                'largestContentfulPaint': 42.0,
                'overallCumulativeLayoutShift': 22.0
            },
            'speedometer2': {}
        },
        'run_id': 'fake_job_id'
    }]

    results2.GenerateResults2(job)
    self.maxDiff = None
    self.assertItemsEqual(mock_bqinsert.call_args_list[0][0][3], expected_rows)

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2, '_InsertBQRows')
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  @mock.patch.object(swarming, 'Swarming')
  @mock.patch.object(commit.Commit, 'GetOrCacheCommitInfo')
  def testTypeDispatch_PushBQ_CH_Speedometer2(self, mock_commit_info,
                                              mock_swarming, mock_json,
                                              mock_render, mock_bqinsert):
    expected_histogram_set = histogram_set.HistogramSet([
        _CreateHistogram('Angular2-TypeScript-TodoMVC', 1),
        _CreateHistogram('AngularJS-TodoMVC', 2),
        _CreateHistogram('BackboneJS-TodoMVC', 3),
        _CreateHistogram('Elm-TodoMVC', 4),
        _CreateHistogram('EmberJS-Debug-TodoMVC', 5),
        _CreateHistogram('EmberJS-TodoMVC', 6),
        _CreateHistogram('Flight-TodoMVC', 7),
        _CreateHistogram('Inferno-TodoMVC', 8),
        _CreateHistogram('jQuery-TodoMVC', 9),
        _CreateHistogram('Preact-TodoMVC', 10),
        _CreateHistogram('React-Redux-TodoMVC', 11),
        _CreateHistogram('React-TodoMVC', 12),
        _CreateHistogram('Vanilla-ES2015-Babel-Webpack-TodoMVC', 13),
        _CreateHistogram('Vanilla-ES2015-TodoMVC', 14),
        _CreateHistogram('VanillaJS-TodoMVC', 15),
        _CreateHistogram('VueJS-TodoMVC', 16)
    ])
    job = _SetupBQTest(mock_commit_info, mock_swarming, mock_render, mock_json,
                       expected_histogram_set, set_device_os=False)

    expected_rows = [{
        'job_start_time': _TEST_START_TIME_STR,
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'swarming_bot_id': 'fake_id',
                'os': ['base_os']
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0,
                'variant': 0
            },
            'checkout': {
                'repo': 'fakerepo',
                'git_hash': 'fakehashA',
                'commit_position': 437745,
                'commit_created': '2021-12-08 00:00:00.000000',
                'branch': 'refs/heads/main'
            }
        },
        'measures': {
            'core_web_vitals': {},
            'speedometer2': {
                'Angular2_TypeScript_TodoMVC': 1,
                'AngularJS_TodoMVC': 2,
                'BackboneJS_TodoMVC': 3,
                'Elm_TodoMVC': 4,
                'EmberJS_Debug_TodoMVC': 5,
                'EmberJS_TodoMVC': 6,
                'Flight_TodoMVC': 7,
                'Inferno_TodoMVC': 8,
                'jQuery_TodoMVC': 9,
                'Preact_TodoMVC': 10,
                'React_Redux_TodoMVC': 11,
                'React_TodoMVC': 12,
                'Vanilla_ES2015_Babel_Webpack_TodoMVC': 13,
                'Vanilla_ES2015_TodoMVC': 14,
                'VanillaJS_TodoMVC': 15,
                'VueJS_TodoMVC': 16
            }
        },
        'run_id': 'fake_job_id'
    }, {
        'job_start_time': _TEST_START_TIME_STR,
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'swarming_bot_id': 'fake_id',
                'os': ['base_os']
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0,
                'variant': 1
            },
            'checkout': {
                'patch_gerrit_revision': 'fake_patch_set',
                'commit_position': 437745,
                'commit_created': '2021-12-08 00:00:00.000000',
                'patch_gerrit_change': 'fake_patch_issue',
                'repo': 'fakeRepo',
                'branch': 'refs/heads/main',
                'git_hash': 'fakehashB'
            }
        },
        'measures': {
            'core_web_vitals': {},
            'speedometer2': {
                'Angular2_TypeScript_TodoMVC': 1,
                'AngularJS_TodoMVC': 2,
                'BackboneJS_TodoMVC': 3,
                'Elm_TodoMVC': 4,
                'EmberJS_Debug_TodoMVC': 5,
                'EmberJS_TodoMVC': 6,
                'Flight_TodoMVC': 7,
                'Inferno_TodoMVC': 8,
                'jQuery_TodoMVC': 9,
                'Preact_TodoMVC': 10,
                'React_Redux_TodoMVC': 11,
                'React_TodoMVC': 12,
                'Vanilla_ES2015_Babel_Webpack_TodoMVC': 13,
                'Vanilla_ES2015_TodoMVC': 14,
                'VanillaJS_TodoMVC': 15,
                'VueJS_TodoMVC': 16
            }
        },
        'run_id': 'fake_job_id'
    }]

    results2.GenerateResults2(job)
    self.maxDiff = None
    self.assertItemsEqual(mock_bqinsert.call_args_list[0][0][3], expected_rows)


  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2, '_InsertBQRows')
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  @mock.patch.object(swarming, 'Swarming')
  @mock.patch.object(commit.Commit, 'GetOrCacheCommitInfo')
  def testTypeDispatch_PushBQ_CH_NoRows(self, mock_commit_info, mock_swarming,
                                        mock_json, mock_render, mock_bqinsert):
    useless_histogram = histogram_module.Histogram('someUselessMetric', 'count')
    useless_histogram.AddSample(42)
    expected_histogram_set = histogram_set.HistogramSet([useless_histogram])
    job = _SetupBQTest(mock_commit_info, mock_swarming, mock_render, mock_json,
                       expected_histogram_set)

    results2.GenerateResults2(job)
    self.assertEqual(1, len(mock_bqinsert.call_args_list))

  @mock.patch.object(results2, '_GcsFileStream', mock.MagicMock())
  @mock.patch.object(results2, '_InsertBQRows')
  @mock.patch.object(results2.render_histograms_viewer,
                     'RenderHistogramsViewer')
  @mock.patch.object(results2, '_JsonFromExecution')
  @mock.patch.object(swarming, 'Swarming')
  @mock.patch.object(commit.Commit, 'GetOrCacheCommitInfo')
  def testTypeDispatch_PushBQ_General(self, mock_commit_info, mock_swarming,
                                      mock_json, mock_render, mock_bqinsert):
    expected_histogram_set = histogram_set.HistogramSet([
        _CreateHistogram('largestContentfulPaint', 42),
        _CreateHistogram('someUselessMetric', 42)
    ])
    job = _SetupBQTest(mock_commit_info, mock_swarming, mock_render, mock_json,
                       expected_histogram_set)

    ck_a = {
        'repo': 'fakerepo',
        'git_hash': 'fakehashA',
        'commit_position': 437745,
        'branch': 'refs/heads/main',
        'commit_created': '2021-12-08 00:00:00.000000'
    }
    ck_b = {
        'patch_gerrit_revision': 'fake_patch_set',
        'commit_position': 437745,
        'patch_gerrit_change': 'fake_patch_issue',
        'repo': 'fakeRepo',
        'branch': 'refs/heads/main',
        'git_hash': 'fakehashB',
        'commit_created': '2021-12-08 00:00:00.000000'
    }

    expected_rows = [
        _CreateGeneralRow(ck_a, 0, 'largestContentfulPaint', [42]),
        _CreateGeneralRow(ck_a, 0, 'someUselessMetric', [42]),
        _CreateGeneralRow(ck_b, 1, 'largestContentfulPaint', [42]),
        _CreateGeneralRow(ck_b, 1, 'someUselessMetric', [42])
    ]

    results2.GenerateResults2(job)
    self.maxDiff = None
    self.assertItemsEqual(mock_bqinsert.call_args_list[1][0][3], expected_rows)


def _CreateGeneralRow(checkout, variant, metric, values):
  return {
      'job_start_time': _TEST_START_TIME_STR,
      'batch_id': 'fake_batch_id',
      'dims': {
          'device': {
              'cfg': 'fake_configuration',
              'swarming_bot_id': 'fake_id',
              'os': ['os1', 'os2']
          },
          'test_info': {
              'story': 'fake_story',
              'benchmark': 'fake_benchmark'
          },
          'pairing': {
              'replica': 0,
              'variant': variant
          },
          'checkout': checkout
      },
      'run_id': 'fake_job_id',
      'metric': metric,
      'values': values
  }


def _CreateHistogram(name, val):
  h = histogram_module.Histogram(name, 'count')
  h.AddSample(val)
  return h


def _SetupBQTest(mock_commit_info, mock_swarming, mock_render, mock_json,
                 expected_histogram_set, set_device_os=True):
  mock_commit_info.return_value = {
      'author': {
          'email': 'author@chromium.org'
      },
      'created': isoparse('2021-12-08'),
      'commit': 'aaa7336',
      'committer': {
          'time': 'Fri Jan 01 00:01:00 2016'
      },
      'message': 'Subject.\n\n'
                 'Commit message.\n'
                 'Reviewed-on: https://foo/c/chromium/src/+/123\n'
                 'Cr-Commit-Position: refs/heads/main@{#437745}',
  }

  test_execution = run_test._RunTestExecution("fake_server", None, None, None,
                                              None, None)
  test_execution._task_id = "fake_task"

  commit_a = commit.Commit("fakerepo", "fakehashA")
  change_a = change.Change([commit_a], variant=0)
  commit_b = commit.Commit("fakeRepo", "fakehashB")
  patch_b = FakePatch("fakePatchServer", "fakePatchNo", "fakePatchRev")
  change_b = change.Change([commit_b], patch_b, variant=1)

  benchmark_arguments = FakeBenchmarkArguments("fake_benchmark", "fake_story")
  job = _JobStub(
      None,
      'fake_job_id',
      None,
      _JobStateFake({
          change_a: [{
              'executions': [
                  test_execution,
                  read_value.ReadValueExecution(
                      'fake_filename', ['fake_filename'], 'fake_metric',
                      'fake_grouping_label', 'fake_trace_or_story', 'avg',
                      'fake_chart', 'https://isolate_server',
                      'deadc0decafef00d')
              ]
          }],
          change_b: [{
              'executions': [
                  test_execution,
                  read_value.ReadValueExecution(
                      'fake_filename', ['fake_filename'], 'fake_metric',
                      'fake_grouping_label', 'fake_trace_or_story', 'avg',
                      'fake_chart', 'https://isolate_server',
                      'deadc0decafef00d')
              ]
          }],
      }),
      benchmark_arguments=benchmark_arguments,
      batch_id="fake_batch_id",
      configuration="fake_configuration")
  histograms = []

  def TraverseHistograms(hists, *args, **kw_args):
    del args
    del kw_args
    for histogram in hists:
      histograms.append(histogram)

  task_mock = mock.Mock()
  bot_dimensions = [
      {
          "key": "device_type",
          "value": "type"
      },
      {
          "key": "os",
          "value": ["base_os"]
      },
      {
          "key": "id",
          "value": ["fake_id"]
      }
  ]
  if set_device_os:
    bot_dimensions.append({
        "key": "device_os",
        "value": ["os1", "os2"]
        })
  task_mock.Result.return_value = {
      "bot_dimensions": bot_dimensions
  }
  mock_swarming.return_value.Task.return_value = task_mock
  mock_render.side_effect = TraverseHistograms
  mock_json.return_value = expected_histogram_set.AsDicts()
  return job


class FakePatch(
    collections.namedtuple('GerritPatch', ('server', 'change', 'revision'))):

  def BuildParameters(self):
    return {
        "patch_gerrit_url": "fake_gerrit_url",
        "project": "fake_project",
        "patch_issue": "fake_patch_issue",
        "patch_set": "fake_patch_set"
    }


class _AttemptFake(object):

  def __init__(self, attempt):
    self._attempt = attempt

  @property
  def executions(self):
    logging.debug('Attempt.executions = %s', self._attempt['executions'])
    return self._attempt['executions']

  def __str__(self):
    return '%s' % (self._attempt,)


class _JobStateFake(object):

  def __init__(self, attempts):
    self._attempts = {
        change: [_AttemptFake(attempt)]
        for change, attempt_list in attempts.items() for attempt in attempt_list
    }
    logging.debug('JobStateFake = %s', self._attempts)

  @property
  def _changes(self):
    changes = list(self._attempts.keys())
    logging.debug('JobStateFake._changes = %s', changes)
    return changes

  def Differences(self):

    def Pairwise(iterable):
      a, b = itertools.tee(iterable)
      next(b, None)
      return itertools.izip(a, b)

    return [(a, b) for a, b in Pairwise(self._attempts.keys())]


class _JobStub(object):

  def __init__(self,
               job_dict,
               job_id,
               comparison_mode,
               state=None,
               batch_id=None,
               configuration=None,
               benchmark_arguments=None):
    self._job_dict = job_dict
    self.comparison_mode = comparison_mode
    self.job_id = job_id
    self.state = state
    self.batch_id = batch_id
    self.configuration = configuration
    self.benchmark_arguments = benchmark_arguments
    self.started_time = _TEST_START_TIME

  def AsDict(self, options=None):
    del options
    return self._job_dict
