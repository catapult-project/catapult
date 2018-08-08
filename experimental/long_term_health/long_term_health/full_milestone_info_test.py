# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv
import os
import tempfile
from unittest import TestCase

from long_term_health import full_milestone_info
from long_term_health import utils
import mock


class TestGetBranchInfo(TestCase):

  @mock.patch('long_term_health.full_milestone_info.GetChromiumLog')
  def testGetBranchInfo(self, get_chromium_log_function):
    # this is an incomplete log result, some attributes are omitted
    get_chromium_log_function.return_value = [{
        'committer': {
            'name': 'chrome-release-bot@chromium.org',
            'email': 'chrome-release-bot@chromium.org',
            'time': 'Fri Apr 13 00:33:52 2018'
        },
        'message': 'Incrementing VERSION to 65.0.3325.230'
    }]
    milestone, branch, version_num, release_date = (
        full_milestone_info.GetBranchInfo('65', '3325'))
    self.assertEqual('65', milestone)
    self.assertEqual('3325', branch)
    self.assertEqual('65.0.3325.230', version_num)
    self.assertEqual('2018-04-13T00:33:52', release_date)


class TestMilestoneInfo(TestCase):

  def setUp(self):
    _, self.csv_path = tempfile.mkstemp('.csv')
    with open(self.csv_path, 'w') as tmp_csv:
      writer = csv.writer(tmp_csv)
      fieldnames = ['milestone', 'branch', 'version_number', 'release_date']
      writer.writerow(fieldnames)
      writer.writerow([13, 234, '13.0.0.250', '2013-07-20T00:39:24'])
      writer.writerow([62, 3202, '62.0.3202.101', '2017-11-17T01:03:27'])
      writer.writerow([103, 2304, '103.0.0.250', '2103-07-20T00:39:24'])

    self.milestone_info = full_milestone_info.MilestoneInfo(self.csv_path)

  def tearDown(self):
    os.remove(self.csv_path)

  def testLatest_milestone(self):
    latest_milestone = self.milestone_info.latest_milestone
    self.assertEqual(103, latest_milestone)

  def testGetLatestMilestoneBeforeDate_normalUsage(self):
    milestone = self.milestone_info.GetLatestMilestoneBeforeDate(
        utils.ParseDate('2017-10-01'))
    self.assertEqual(13, milestone)

  def testGetLatestMilestoneBeforeDate_lookUpError(self):
    with self.assertRaises(LookupError):
      self.milestone_info.GetLatestMilestoneBeforeDate(
          utils.ParseDate('2013-07-20'))

  def testGetEarliestMilestoneAfterDate(self):
    version = self.milestone_info.GetEarliestMilestoneAfterDate(
        utils.ParseDate('2017-12-01'))
    self.assertEqual(103, version)

  def testGetEarliestMilestoneAfterDate_lookUpError(self):
    with self.assertRaises(LookupError):
      self.milestone_info.GetEarliestMilestoneAfterDate(
          utils.ParseDate('2200-12-01'))

  def testGetVersionNumberFromMilestone(self):
    self.assertEqual(
        '13.0.0.250', self.milestone_info.GetVersionNumberFromMilestone(13))
    self.assertEqual(
        '62.0.3202.101', self.milestone_info.GetVersionNumberFromMilestone(62))
    self.assertEqual(
        '103.0.0.250', self.milestone_info.GetVersionNumberFromMilestone(103))

