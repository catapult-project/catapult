# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for bisect_group module."""

import json
import unittest

import webapp2
import webtest

from dashboard import bisect_group
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data


class BisectGroupTest(testing_common.TestCase):

  def setUp(self):
    super(BisectGroupTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/bisect_group', bisect_group.BisectGroupHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddSampleData(self):
    """Adds sample data and returns a list of sample Anomaly keys."""
    testing_common.AddDataToMockDataStore(
        ['master'], ['linux-release', 'android-motoe'],
        {
            'page_cycler.moz': {'cold_times': {'page_load_time': {}}},
            'cc_perftests': {'foo': {'bar': {}}},
        })
    return [
        # 0: 200% regression in page_cycler.moz on linux, 201:300
        self._AddAnomaly(
            'master/linux-release/page_cycler.moz/cold_times/page_load_time',
            start_revision=100201, end_revision=100300,
            median_before_anomaly=50, median_after_anomaly=150,
            bug_id=1234, is_improvement=False),
        # 1: 100% regression in page_cycler.moz on android, 221:320
        self._AddAnomaly(
            'master/android-motoe/page_cycler.moz/cold_times/page_load_time',
            start_revision=100221, end_revision=100320,
            median_before_anomaly=50, median_after_anomaly=100,
            bug_id=1234, is_improvement=False),
        # 2: 50% regression in cc_perftests on linux, 181:280
        self._AddAnomaly(
            'master/linux-release/cc_perftests/foo/bar',
            start_revision=100181, end_revision=100280,
            median_before_anomaly=50, median_after_anomaly=75,
            bug_id=2000, is_improvement=False),
    ]

  def _AddAnomaly(self, test_path, **properties):
    """Adds an Anomaly  and returns its key."""
    test_key = utils.TestKey(test_path)
    return anomaly.Anomaly(test=test_key, **properties).put()

  def testGet_WithBugID(self):
    """Tests a request for parameters of a group of alerts specified by key."""
    self._AddSampleData()
    response = self.testapp.get('/bisect_group?bug_id=1234')
    # Linux is used since the regression is larger on Linux.
    expected_parameters = {
        'bisect_bot': 'linux_perf_bisect',
        'command': ('tools/perf/run_benchmark -v '
                    '--browser=release '
                    'page_cycler.moz'),
        'metric': 'cold_times/page_load_time',
        'good_revision': 100220,
        'bad_revision': 100300,
    }
    self.assertEqual(expected_parameters, json.loads(response.body))

  def testGet_WithKeys(self):
    """Tests a request for parameters of a group of alerts specified by key."""
    keys = self._AddSampleData()
    response = self.testapp.get('/bisect_group?keys=%s,%s' %
                                (keys[1].urlsafe(), keys[2].urlsafe()))
    # Android is used, since the regression was larger on Android.
    expected_parameters = {
        'bisect_bot': 'android_motoe_perf_bisect',
        'command': ('tools/perf/run_benchmark -v '
                    '--browser=android-chrome-shell '
                    'page_cycler.moz'),
        'metric': 'cold_times/page_load_time',
        'good_revision': 100220,
        'bad_revision': 100280,
    }
    self.assertEqual(expected_parameters, json.loads(response.body))

  def testGet_NoParamsGivesError_ReturnsError(self):
    """Tests a bare request to /bisect_group with no parameters."""
    # Not giving required parameters is considered "invalid input", status 400.
    self.testapp.get('/bisect_group', status=400)

  def testChooseRevisionRange_InvalidRevisionNum_UsesCommitHashes(self):
    """Tests that git hashes are gotten if revision is timestamp."""
    testing_common.AddDataToMockDataStore(
        ['MyMaster'], ['win'], {'sunspider': {'Total': {}}})
    test_key = utils.TestKey('MyMaster/win/sunspider/Total')
    parent_key = utils.GetTestContainerKey(test_key)
    r1 = '074b44b4f25dfd3e37651ed91d56674f3a740f24'
    r2 = 'ce6fede39f55d8328f7eadaa5bd931552d5b6c07'
    graph_data.Row(parent=parent_key, id=1000000100, r_chromium=r1,
                   value=1).put()
    graph_data.Row(parent=parent_key, id=1000000200, r_chromium=r2,
                   value=1).put()
    anomaly_entity = anomaly.Anomaly(
        test=test_key, start_revision=1000000101, end_revision=1000000200,
        median_before_anomaly=50, median_after_anomaly=150,
        bug_id=1234, is_improvement=False)

    good, bad = bisect_group.ChooseRevisionRange([anomaly_entity])
    self.assertEqual(r1, good)
    self.assertEqual(r2, bad)

  def testChooseRevisionRange_InvalidRevisionNumNoHash_ReturnsNone(self):
    """Tests the handling of revision ranges with invalid revisions."""
    testing_common.AddDataToMockDataStore(
        ['MyMaster'], ['win'], {'sunspider': {'Total': {}}})
    test_key = utils.TestKey('MyMaster/win/sunspider/Total')
    anomaly_entity = anomaly.Anomaly(
        test=test_key, start_revision=1000010000, end_revision=1000020000,
        median_before_anomaly=50, median_after_anomaly=150,
        bug_id=1234, is_improvement=False)

    # The revisions don't appear to be SVN revisions and there are no
    # corresponding points in the datastore, so None is returned.
    good, bad = bisect_group.ChooseRevisionRange([anomaly_entity])
    self.assertIsNone(good)
    self.assertIsNone(bad)

  def testGet_NonOverlappingRevision_NoConfigReturned(self):
    """Tests the getting of a config with some invalid inputs."""
    keys = self._AddSampleData()
    other_key = self._AddAnomaly(
        'master/linux-release/cc_perftests/foo/bar',
        start_revision=200, end_revision=300,
        median_before_anomaly=50, median_after_anomaly=150,
        bug_id=1234, is_improvement=False)

    response = self.testapp.get('/bisect_group?keys=%s,%s' %
                                (keys[1].urlsafe(), other_key.urlsafe()))
    # The revision range was non-overlapping, so no config is returned.
    expected_parameters = {}
    self.assertEqual(expected_parameters, json.loads(response.body))


if __name__ == '__main__':
  unittest.main()
