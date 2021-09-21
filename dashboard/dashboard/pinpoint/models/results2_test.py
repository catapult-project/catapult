# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
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
from tracing.value import histogram_set
from tracing.value import histogram as histogram_module

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
  def testTypeDispatch_PushBQ(self, mock_swarming, mock_json, mock_render,
                              mock_bqinsert):

    test_execution = run_test._RunTestExecution("fake_server", None, None, None,
                                                None, None)
    test_execution._task_id = "fake_task"

    commit_a = commit.Commit("fakerepo", "fakehashA")
    change_a = change.Change([commit_a])
    commit_b = commit.Commit("fakeRepo", "fakehashB")
    patch_b = FakePatch("fakePatchServer", "fakePatchNo", "fakePatchRev")
    change_b = change.Change([commit_b], patch_b)

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
    task_mock.Result.return_value = {
        "bot_dimensions": {
            "device_type": "type",
            "device_os": "os"
        }
    }
    mock_swarming.return_value.Task.return_value = task_mock
    mock_render.side_effect = TraverseHistograms
    lcp_histogram = histogram_module.Histogram('largestContentfulPaint',
                                               'count')
    lcp_histogram.AddSample(42)
    fcp_histogram = histogram_module.Histogram('timeToFirstContentfulPaint',
                                               'count')
    fcp_histogram.AddSample(11)
    cls_histogram = histogram_module.Histogram('overallCumulativeLayoutShift',
                                               'count')
    cls_histogram.AddSample(22)
    tbt_histogram = histogram_module.Histogram('totalBlockingTime', 'count')
    tbt_histogram.AddSample(33)
    expected_histogram_set = histogram_set.HistogramSet(
        [lcp_histogram, fcp_histogram, cls_histogram, tbt_histogram])
    mock_json.return_value = expected_histogram_set.AsDicts()

    expected_rows = [{
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'os': 'os'
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0
            },
            'checkout': {
                'repo': 'fakeRepo',
                'git_hash': 'fakehashB',
                'patch_gerrit_revision': 'fake_patch_set',
                'patch_gerrit_change': 'fake_patch_issue'
            }
        },
        'measures': {
            'core_web_vitals': {
                'timeToFirstContentfulPaint': 11.0,
                'largestContentfulPaint': 42.0,
                'overallCumulativeLayoutShift': 22.0,
                'totalBlockingTime': 33
            }
        },
        'run_id': 'fake_job_id'
    }, {
        'batch_id': 'fake_batch_id',
        'dims': {
            'device': {
                'cfg': 'fake_configuration',
                'os': 'os'
            },
            'test_info': {
                'story': 'fake_story',
                'benchmark': 'fake_benchmark'
            },
            'pairing': {
                'replica': 0
            },
            'checkout': {
                'repo': 'fakerepo',
                'git_hash': 'fakehashA'
            }
        },
        'measures': {
            'core_web_vitals': {
                'timeToFirstContentfulPaint': 11.0,
                'largestContentfulPaint': 42.0,
                'overallCumulativeLayoutShift': 22.0,
                'totalBlockingTime': 33
            }
        },
        'run_id': 'fake_job_id'
    }]

    results2.GenerateResults2(job)
    mock_bqinsert.assert_called_once_with('chromeperf', 'pinpoint_export_test',
                                          'pinpoint_results', expected_rows)


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

  def AsDict(self, options=None):
    del options
    return self._job_dict
