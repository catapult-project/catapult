# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from services import dashboard_service


class PerfDashboardCommunicator(object):
  # TODO(crbug.com/890691): Remove this class and merge functionality with
  # dashboard_service module instead.
  def __init__(self):
    self.dashboard = dashboard_service

  def GetBugData(self, bug_ids):
    """Yields data for a given bug id or sequence of bug ids."""
    if not hasattr(bug_ids, '__iter__'):
      bug_ids = [bug_ids]
    for bug_id in bug_ids:
      yield self.dashboard.Request('/bugs/%d' % bug_id)

  def IterAlertData(self, test_suite, sheriff, days=30):
    """Returns alerts for the given test_suite.

    Args:
      test_suite: String with test suite (benchmark) to get paths for.
      sheriff: Include only test paths monitored by the given sheriff rotation,
          use 'all' to return all test pathds regardless of rotation.
      days: Only return alerts which are at most this number of days old.

    Yields:
      Data for all requested alerts in chunks.
    """
    min_timestamp = datetime.datetime.now() - datetime.timedelta(days=days)
    params = {
        'test_suite': test_suite,
        'min_timestamp': min_timestamp.isoformat(),
        'limit': 1000,
    }
    if sheriff != 'all':
      params['sheriff'] = sheriff
    while True:
      response = self.dashboard.Request('/alerts', params=params)
      yield response
      if 'next_cursor' in response:
        params['cursor'] = response['next_cursor']
      else:
        return
