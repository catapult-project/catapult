# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import unittest

from dashboard.api import api_auth
from dashboard.api import list_timeseries
from dashboard.common import testing_common
from dashboard.models import sheriff


class ListTimeseriesTest(testing_common.TestCase):

  def setUp(self):
    super(ListTimeseriesTest, self).setUp()
    self.SetUpApp([(r'/api/list_timeseries/(.*)',
                    list_timeseries.ListTimeseriesHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])

  def _AddData(self):
    """Adds sample TestMetadata entities and returns their keys."""
    testing_common.AddTests(['ChromiumPerf'], ['linux', 'win', 'mac'], {
        'v8': {
            'sunspider': {'Total': {}},
            'octane': {'Total': {}},
            'memory': {'Total': {}},
        },
        'page_cycler': {
            'warm': {'cnn': {}, 'facebook': {}, 'yahoo': {}},
            'cold': {'nytimes': {}, 'cnn': {}, 'yahoo': {}}
        }
    })

    sheriff.Sheriff(
        id='V8 Perf Sheriff', email='v8@v8.com', patterns=[
            '*/*/v8/sunspider/*',
            '*/*/v8/octane/*',
            '*/*/v8/octane'
        ]).put()

    sheriff.Sheriff(
        id='V8 Memory Sheriff', email='v8-memory@v8.com', patterns=[
            '*/*/v8/memory/*',
        ]).put()

    sheriff.Sheriff(
        id='Chromium Perf Sheriff', email='loadin@Loading.org', patterns=[
            '*/mac/page_cycler/*/*',
            '*/*/page_cycler/warm/*'
        ]).put()
    for bot in ['linux', 'win', 'mac']:
      for path in ['sunspider/Total', 'octane/Total', 'octane', 'memory/Total']:
        testing_common.AddRows(
            'ChromiumPerf/%s/v8/%s' % (bot, path), [200, 300, 400, 500])
      for page in ['warm/cnn',
                   'warm/facebook',
                   'warm/yahoo',
                   'cold/nytimes',
                   'cold/cnn',
                   'cold/yahoo']:
        testing_common.AddRows(
            'ChromiumPerf/%s/page_cycler/%s' % (bot, page), [100, 200, 300])

  def testPost_External(self):
    self.SetCurrentUserOAuth(testing_common.EXTERNAL_USER)
    self._AddData()

    response = self.Post('/api/list_timeseries/v8', {'sheriff': 'all'})
    paths = json.loads(response.body)
    self.assertEqual(set([
        'ChromiumPerf/mac/v8/sunspider/Total',
        'ChromiumPerf/mac/v8/octane/Total',
        'ChromiumPerf/mac/v8/octane',
        'ChromiumPerf/mac/v8/memory/Total',
        'ChromiumPerf/linux/v8/sunspider/Total',
        'ChromiumPerf/linux/v8/octane/Total',
        'ChromiumPerf/linux/v8/octane',
        'ChromiumPerf/linux/v8/memory/Total',
        'ChromiumPerf/win/v8/sunspider/Total',
        'ChromiumPerf/win/v8/octane/Total',
        'ChromiumPerf/win/v8/octane',
        'ChromiumPerf/win/v8/memory/Total',
    ]), set(paths))

  def testPost_NoSheriff_IgnoresV8Perf(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()

    response = self.Post('/api/list_timeseries/v8')
    paths = json.loads(response.body)
    self.assertEqual([], paths)

  def testPost_NoSheriff_ListsChromiumPerf(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()

    response = self.Post('/api/list_timeseries/page_cycler')
    paths = json.loads(response.body)
    self.assertEqual(set([
        'ChromiumPerf/mac/page_cycler/warm/cnn',
        'ChromiumPerf/mac/page_cycler/warm/facebook',
        'ChromiumPerf/mac/page_cycler/warm/yahoo',
        'ChromiumPerf/mac/page_cycler/cold/nytimes',
        'ChromiumPerf/mac/page_cycler/cold/cnn',
        'ChromiumPerf/mac/page_cycler/cold/yahoo',
        'ChromiumPerf/linux/page_cycler/warm/cnn',
        'ChromiumPerf/linux/page_cycler/warm/facebook',
        'ChromiumPerf/linux/page_cycler/warm/yahoo',
        'ChromiumPerf/win/page_cycler/warm/cnn',
        'ChromiumPerf/win/page_cycler/warm/facebook',
        'ChromiumPerf/win/page_cycler/warm/yahoo',
    ]), set(paths))

  def testPost_V8Sheriff_ListsV8Perf(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()

    response = self.Post(
        '/api/list_timeseries/v8', {'sheriff': 'V8 Perf Sheriff'})
    paths = json.loads(response.body)
    self.assertEqual(set([
        'ChromiumPerf/mac/v8/sunspider/Total',
        'ChromiumPerf/mac/v8/octane/Total',
        'ChromiumPerf/mac/v8/octane',
        'ChromiumPerf/linux/v8/sunspider/Total',
        'ChromiumPerf/linux/v8/octane/Total',
        'ChromiumPerf/linux/v8/octane',
        'ChromiumPerf/win/v8/sunspider/Total',
        'ChromiumPerf/win/v8/octane/Total',
        'ChromiumPerf/win/v8/octane',
    ]), set(paths))

  def testPost_AllSheriff_ListsAllV8Perf(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    self._AddData()

    response = self.Post('/api/list_timeseries/v8', {'sheriff': 'all'})
    paths = json.loads(response.body)
    self.assertEqual(set([
        'ChromiumPerf/mac/v8/sunspider/Total',
        'ChromiumPerf/mac/v8/octane/Total',
        'ChromiumPerf/mac/v8/octane',
        'ChromiumPerf/mac/v8/memory/Total',
        'ChromiumPerf/linux/v8/sunspider/Total',
        'ChromiumPerf/linux/v8/octane/Total',
        'ChromiumPerf/linux/v8/octane',
        'ChromiumPerf/linux/v8/memory/Total',
        'ChromiumPerf/win/v8/sunspider/Total',
        'ChromiumPerf/win/v8/octane/Total',
        'ChromiumPerf/win/v8/octane',
        'ChromiumPerf/win/v8/memory/Total',
    ]), set(paths))


if __name__ == '__main__':
  unittest.main()
