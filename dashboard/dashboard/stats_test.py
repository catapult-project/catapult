# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import webapp2
import webtest

from google.appengine.api import users

from dashboard import stats
from dashboard import testing_common
from dashboard import utils
from dashboard import xsrf
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import sheriff

_MOCK_DATA = [
    ['ChromiumPerf'],
    ['win7', 'mac'],
    {
        'moz': {
            'times': {
                'page_load_time': {},
                'page_load_time_ref': {},
            }
        },
        'octane': {
            'Total': {
                'Score': {},
                'Score_ref': {},
            }
        }
    }
]

# Sample row data to use in tests for around-revision stats below.
_WIN7_MOZ = [100] * 20 + [200] * 20
_WIN7_OCTANE = [100, 200] * 10 + [300, 400] * 10
_MAC_MOZ = [100] * 40
_MAC_OCTANE = [300, 500] * 10 + [50, 30] * 10


class StatsTest(testing_common.TestCase):

  def setUp(self):
    super(StatsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/stats', stats.StatsHandler),
        ('/stats_around_revision', stats.StatsAroundRevisionHandler),
        ('/stats_for_alerts', stats.StatsForAlertsHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)

  def _AddMockData(self):
    """Adds data which will be used in the around-revision stats tests below."""
    sheriff.Sheriff(
        id='Chromium Perf Sheriff',
        email='sullivan@chromium.org',
        patterns=['*/*/*/*/page_load_time', '*/*/*/*/Score']).put()
    testing_common.AddTests(*_MOCK_DATA)
    test_paths = [
        'ChromiumPerf/win7/moz/times/page_load_time',
        'ChromiumPerf/win7/octane/Total/Score',
        'ChromiumPerf/mac/moz/times/page_load_time',
        'ChromiumPerf/mac/octane/Total/Score',
    ]
    test_keys = map(utils.TestKey, test_paths)
    row_data = [_WIN7_MOZ, _WIN7_OCTANE, _MAC_MOZ, _MAC_OCTANE]
    for index, test_key in enumerate(test_keys):
      test = test_key.get()
      if test_key.string_id() == 'page_load_time':
        test.improvement_direction = anomaly.DOWN
      else:
        test.improvement_direction = anomaly.UP
      test.put()
      parent_key = utils.GetTestContainerKey(test_key)
      for r in range(15000, 15080, 2):
        v = row_data[index][(r - 15000) / 2]
        graph_data.Row(id=r, parent=parent_key, value=v).put()

  def _AddMockAlertSummaryData(self):
    """Adds data to be used in the alert-summary stats tests below."""
    correct_sheriff = sheriff.Sheriff(
        id='Chromium Perf Sheriff', patterns=[]).put()
    wrong_sheriff = sheriff.Sheriff(
        id='Some other sheriff', patterns=[]).put()

    linux_sunspider = 'ChromiumPerf/linux-release/sunspider/Total'
    linux_octane = 'ChromiumPerf/linux-release/octane/Total'
    linux_media = 'ChromiumPerf/linux-release/media.tough_media_cases/Total'
    windows_sunspider = 'ChromiumPerf/windows/sunspider/Total'
    windows_octane = 'ChromiumPerf/windows/octane/Total'

    # Should not be included: too early.
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 1),
        test=utils.TestKey(linux_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=100.5).put()

    # Should not be included: too late.
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 6, 17),
        test=utils.TestKey(linux_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=100.5).put()

    # Should not be included: wrong sheriff.
    anomaly.Anomaly(
        sheriff=wrong_sheriff,
        timestamp=datetime.datetime(2013, 5, 11),
        test=utils.TestKey(linux_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=100.5).put()

    # Everything below should be included.
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 12),
        test=utils.TestKey(linux_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=100.5).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 12),
        test=utils.TestKey(linux_octane),
        median_before_anomaly=100,
        median_after_anomaly=101.5,
        bug_id=-1).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 12),
        test=utils.TestKey(linux_media),
        median_before_anomaly=100,
        median_after_anomaly=101.5,
        bug_id=-2).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 12),
        test=utils.TestKey(windows_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=104.5,
        bug_id=12345).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 12),
        test=utils.TestKey(windows_octane),
        median_before_anomaly=100,
        median_after_anomaly=600,
        bug_id=12345).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 15),
        test=utils.TestKey(linux_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=200).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 20),
        test=utils.TestKey(windows_sunspider),
        median_before_anomaly=100,
        median_after_anomaly=115,
        bug_id=12345).put()
    anomaly.Anomaly(
        sheriff=correct_sheriff,
        timestamp=datetime.datetime(2013, 5, 21),
        test=utils.TestKey(windows_octane),
        median_before_anomaly=100,
        median_after_anomaly=104).put()

  def testPost_NonInternalUser_ShowsErrorMessage(self):
    """Tests that the stats page is only shown when logged in."""
    self.SetCurrentUser('foo@chromium.org')
    response = self.testapp.get('/stats')
    self.assertIn('Only logged-in internal users', response.body)

    # Same thing if an xsrf token is given.
    response = self.testapp.post('/stats', {
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertIn('Only logged-in internal users', response.body)

  def testPost_AlertSummary(self):
    """Tests generation of alert_summary statistics."""
    self._AddMockAlertSummaryData()

    # The user must be an internal user.
    self.SetCurrentUser('internal@chromium.org')

    # Make the initial request to generate statistics.
    response = self.testapp.post(
        '/stats', {
            'type': 'alert_summary',
            'start_date': '2013-05-10',
            'end_date': '2013-06-07',
            'sheriff': 'Chromium Perf Sheriff',
            'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
        })

    # After making this request, the user is given a page that shows
    # progress of generated statistics.
    redirect_uri = response.location.replace('http://localhost', '')
    response = self.testapp.get(redirect_uri)
    self.assertIn('Waiting (0 of 29)', response.body)

    # After the initial request, a StatContainer entity is created
    # and initialized, but there are no individual stats yet.
    containers = stats.StatContainer.query().fetch()
    self.assertEqual(1, len(containers))
    self.assertEqual('alert_summary', containers[0].stat_type)
    self.assertEqual(29, containers[0].num_stats)
    individual_stats = stats.IndividualStat.query().fetch()
    self.assertEqual(0, len(individual_stats))

    # All of the individual stats are generated by tasks in the task queue.
    # After all of these tasks are done, the individual stats are created.
    self.ExecuteTaskQueueTasks('/stats_for_alerts', stats._QUEUE_NAME)
    individual_stats = stats.IndividualStat.query().fetch()
    self.assertEqual(29, len(individual_stats))
    individual_stats.sort(key=_IndividualStatTimeInt)
    days_with_data = [2, 5, 10, 11]
    for index, stat in enumerate(individual_stats):
      if index in days_with_data:
        continue
      self.assertEqual(['date'], stat.details.keys())

    may_12 = individual_stats[2]
    details = may_12.details
    self.assertEqual({'ChromiumPerf/linux-release': 3,
                      'ChromiumPerf/windows': 2},
                     details['bots'])
    self.assertEqual({'media.tough_media_cases': 1, 'sunspider': 2,
                      'octane': 2}, details['test_suites'])
    self.assertEqual({'media.tough_media_cases/Total': 1, 'sunspider/Total': 2,
                      'octane/Total': 2}, details['tests'])
    self.assertEqual({'-1': 1, '-2': 1, '12345': 2}, details['bug_ids'])
    self.assertEqual({'01%': 1, '02%': 2, '05%': 1, 'largest': 1},
                     details['percent_changed_buckets'])

    may_15 = individual_stats[5]
    details = may_15.details
    self.assertEqual({'ChromiumPerf/linux-release': 1}, details['bots'])
    self.assertEqual({'sunspider': 1}, details['test_suites'])
    self.assertEqual({'sunspider/Total': 1}, details['tests'])
    self.assertIsNone(details.get('bug_ids'))
    self.assertEqual({'largest': 1}, details['percent_changed_buckets'])

    may_20 = individual_stats[10]
    details = may_20.details
    self.assertEqual({'12345': 1}, details['bug_ids'])
    self.assertEqual({'20%': 1}, details['percent_changed_buckets'])

    may_21 = individual_stats[11]
    details = may_21.details
    self.assertEqual({'ChromiumPerf/windows': 1}, details['bots'])

  def testPost_AroundRevision(self):
    """Tests generation of around_revision statistics."""
    self._AddMockData()
    self.SetCurrentUser('internal@chromium.org')

    response = self.testapp.post('/stats', [
        ('type', 'around_revision'),
        ('name', 'Testing'),
        ('rev', '15040'),
        ('num_around', '10'),
        ('bots', 'win7'),
        ('bots', 'mac'),
        ('xsrf_token', xsrf.GenerateToken(users.get_current_user())),
    ])

    # Before the task queue tasks are executed, the user should be redirected
    # to a page that says it's waiting and 0 of 4 are processed. The container
    # should exist, but no children.
    redirect_uri = response.location.replace('http://localhost', '')
    response = self.testapp.get(redirect_uri)
    self.assertIn('Waiting (0 of 4)', response.body)
    containers = stats.StatContainer.query().fetch()
    self.assertEqual(1, len(containers))
    self.assertEqual('around_revision', containers[0].stat_type)
    self.assertEqual(4, containers[0].num_stats)
    self.assertEqual({'name': 'Testing', 'revision': 15040, 'num_around': 10},
                     containers[0].summary)
    individual_stats = stats.IndividualStat.query().fetch()
    self.assertEqual(0, len(individual_stats))
    self.ExecuteTaskQueueTasks('/stats_around_revision', stats._QUEUE_NAME)

    # After executing all task queue tasks, the individual stats should exist
    # and be filled in correctly.
    individual_stats = stats.IndividualStat.query().fetch()
    self.assertEqual(4, len(individual_stats))
    self.assertEqual('ChromiumPerf/mac/moz/times/page_load_time',
                     individual_stats[0].details['test_path'])
    self.assertEqual(15040, individual_stats[0].details['actual_revision'])
    self.assertEqual('0.00',
                     individual_stats[0].details['median_percent_improved'])
    self.assertEqual('100.00', individual_stats[0].details['median_before'])
    self.assertEqual('100.00', individual_stats[0].details['median_after'])
    self.assertEqual('0.00',
                     individual_stats[0].details['mean_percent_improved'])
    self.assertEqual('100.00', individual_stats[0].details['mean_before'])
    self.assertEqual('100.00', individual_stats[0].details['mean_after'])
    self.assertEqual('0.00', individual_stats[0].details['std'])

    self.assertEqual('ChromiumPerf/mac/octane/Total/Score',
                     individual_stats[1].details['test_path'])
    self.assertEqual(15040, individual_stats[1].details['actual_revision'])
    self.assertEqual('-90.00',
                     individual_stats[1].details['median_percent_improved'])
    self.assertEqual('400.00', individual_stats[1].details['median_before'])
    self.assertEqual('40.00', individual_stats[1].details['median_after'])
    self.assertEqual('-90.00',
                     individual_stats[1].details['mean_percent_improved'])
    self.assertEqual('400.00', individual_stats[1].details['mean_before'])
    self.assertEqual('40.00', individual_stats[1].details['mean_after'])
    self.assertEqual('193.52', individual_stats[1].details['std'])

    self.assertEqual('ChromiumPerf/win7/moz/times/page_load_time',
                     individual_stats[2].details['test_path'])
    self.assertEqual(15040, individual_stats[2].details['actual_revision'])
    self.assertEqual('-100.00',
                     individual_stats[2].details['median_percent_improved'])
    self.assertEqual('100.00', individual_stats[2].details['median_before'])
    self.assertEqual('200.00', individual_stats[2].details['median_after'])
    self.assertEqual('-100.00',
                     individual_stats[2].details['mean_percent_improved'])
    self.assertEqual('100.00', individual_stats[2].details['mean_before'])
    self.assertEqual('200.00', individual_stats[2].details['mean_after'])
    self.assertEqual('50.00', individual_stats[2].details['std'])

    self.assertEqual('ChromiumPerf/win7/octane/Total/Score',
                     individual_stats[3].details['test_path'])
    self.assertEqual(15040, individual_stats[3].details['actual_revision'])
    self.assertEqual(
        '133.33', individual_stats[3].details['median_percent_improved'])
    self.assertEqual('150.00', individual_stats[3].details['median_before'])
    self.assertEqual('350.00', individual_stats[3].details['median_after'])
    self.assertEqual('133.33',
                     individual_stats[3].details['mean_percent_improved'])
    self.assertEqual('150.00', individual_stats[3].details['mean_before'])
    self.assertEqual('350.00', individual_stats[3].details['mean_after'])
    self.assertEqual('111.80', individual_stats[3].details['std'])

    # Since the data is now filled in correctly, the stats should be shown
    # when reloading the URI with the key.
    response = self.testapp.get(redirect_uri)
    self.assertIn('Testing: Changes around revision 15040 (10 points',
                  response.body)

    # And reloading the stats page should include these stats in the list.
    response = self.testapp.get('/stats')
    self.assertIn(
        ('<a href="/stats?key=%s">Testing: Changes around revision 15040 '
         '(10 points each direction)</a>' % containers[0].key.urlsafe()),
        response.body)

  def testPost_AroundRevisionWithOneBot(self):
    """Tests generation of around_revision stats for only one bot."""
    self._AddMockData()
    self.SetCurrentUser('internal@chromium.org')

    # Post a request to get around_revision stats.
    self.testapp.post('/stats', {
        'bots': 'win7',
        'type': 'around_revision',
        'rev': '15040',
        'num_around': '10',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.ExecuteTaskQueueTasks('/stats_around_revision', stats._QUEUE_NAME)

    containers = stats.StatContainer.query().fetch()
    self.assertEqual(1, len(containers))
    self.assertEqual('around_revision', containers[0].stat_type)
    self.assertEqual(2, containers[0].num_stats)
    self.assertEqual({'name': None, 'revision': 15040, 'num_around': 10},
                     containers[0].summary)
    individual_stats = stats.IndividualStat.query().fetch()
    self.assertEqual(2, len(individual_stats))
    self.assertEqual('ChromiumPerf/win7/moz/times/page_load_time',
                     individual_stats[0].details['test_path'])
    self.assertEqual('ChromiumPerf/win7/octane/Total/Score',
                     individual_stats[1].details['test_path'])


def _IndividualStatTimeInt(individual_stat):
  date = individual_stat.details['date']
  return (int(date.split('-')[0]) * 10000 +
          int(date.split('-')[1]) * 100 +
          int(date.split('-')[2]))


if __name__ == '__main__':
  unittest.main()
