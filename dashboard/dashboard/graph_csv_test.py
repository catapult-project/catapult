# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for graph_csv module."""

import csv
import StringIO
import unittest

import webapp2
import webtest

from dashboard import datastore_hooks
from dashboard import graph_csv
from dashboard import ip_whitelist
from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data


class GraphCsvTest(testing_common.TestCase):

  def setUp(self):
    super(GraphCsvTest, self).setUp()
    app = webapp2.WSGIApplication([('/graph_csv', graph_csv.GraphCsvHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def _SetUpIpWhitelist(self):
    """Adds an IP whitelist and returns whitelisted IP."""
    whitelisted_ip = '123.45.67.89'
    whitelist = ip_whitelist.IpWhitelist(
        id=ip_whitelist.WHITELIST_KEY, ips=[whitelisted_ip])
    whitelist.put()
    return whitelisted_ip

  def _AddMockData(self):
    master = graph_data.Master(id='ChromiumPerf').put()
    bots = []
    for name in ['win7', 'mac']:
      bot = graph_data.Bot(id=name, parent=master).put()
      bots.append(bot)
      test = graph_data.Test(id='dromaeo', parent=bot).put()
      dom_test = graph_data.Test(id='dom', parent=test, has_rows=True).put()
      test_container_key = utils.GetTestContainerKey(dom_test)
      for i in range(15000, 16000, 5):
        graph_data.Row(parent=test_container_key, id=i, value=float(i * 2.5),
                       error=(i + 5)).put()

  def _AddMockInternalData(self):
    master = graph_data.Master(id='ChromiumPerf').put()
    bots = []
    for name in ['win7', 'mac']:
      bot = graph_data.Bot(id=name, parent=master, internal_only=True).put()
      bots.append(bot)
      test = graph_data.Test(id='dromaeo', parent=bot, internal_only=True).put()
      dom_test = graph_data.Test(id='dom', parent=test, has_rows=True).put()
      test_container_key = utils.GetTestContainerKey(dom_test)
      for i in range(1, 50):
        graph_data.Row(
            parent=test_container_key, id=i, value=float(i * 2), error=(i + 10),
            internal_only=True).put()

  def _CheckGet(self, result_query, expected_result, whitelisted_ip=''):
    """Asserts that the given query has the given CSV result.

    Args:
      result_query: The path and query string to request.
      expected_result: The expected table of values (list of lists).
      whitelisted_ip: The IP address to set as request remote address.
    """
    response_rows = []
    response = self.testapp.get(
        result_query, extra_environ={'REMOTE_ADDR': whitelisted_ip})
    for row in csv.reader(StringIO.StringIO(response.body)):
      response_rows.append(row)
    self.assertEqual(expected_result, response_rows)

  def testGetCsv(self):
    self._AddMockData()
    response = self.testapp.get(
        '/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom')
    for index, row, in enumerate(csv.reader(StringIO.StringIO(response.body))):
      # Skip the headers
      if index > 0:
        expected_rev = str(15000 + ((index - 1) * 5))
        expected_value = str(int(expected_rev) * 2.5)
        self.assertEqual([expected_rev, expected_value], row)

  def testPost(self):
    self._AddMockData()
    response = self.testapp.post(
        '/graph_csv?', {'test_path': 'ChromiumPerf/win7/dromaeo/dom'})
    for index, row, in enumerate(csv.reader(StringIO.StringIO(response.body))):
      # Skip the headers
      if index > 0:
        expected_rev = str(15000 + ((index - 1) * 5))
        expected_value = str(int(expected_rev) * 2.5)
        self.assertEqual([expected_rev, expected_value], row)

  def testRevNumRows(self):
    self._AddMockData()
    query = ('/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&'
             'rev=15270&num_points=5')
    expected = [
        ['revision', 'value'],
        ['15250', '38125.0'],
        ['15255', '38137.5'],
        ['15260', '38150.0'],
        ['15265', '38162.5'],
        ['15270', '38175.0'],
    ]
    self._CheckGet(query, expected)

  def testAttrRows(self):
    self._AddMockData()
    query = ('/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&'
             'rev=15270&num_points=5&attr=revision,error,value')
    expected = [
        ['revision', 'error', 'value'],
        ['15250', '15255.0', '38125.0'],
        ['15255', '15260.0', '38137.5'],
        ['15260', '15265.0', '38150.0'],
        ['15265', '15270.0', '38162.5'],
        ['15270', '15275.0', '38175.0'],
    ]
    self._CheckGet(query, expected)
    query = ('/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&'
             'rev=15270&num_points=5&attr=value')
    expected = [
        ['value'],
        ['38125.0'],
        ['38137.5'],
        ['38150.0'],
        ['38162.5'],
        ['38175.0'],
    ]
    self._CheckGet(query, expected)
    query = ('/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&'
             'num_points=5&attr=revision,random,value')
    expected = [
        ['revision', 'random', 'value'],
        ['15975', '', '39937.5'],
        ['15980', '', '39950.0'],
        ['15985', '', '39962.5'],
        ['15990', '', '39975.0'],
        ['15995', '', '39987.5'],
    ]
    self._CheckGet(query, expected)

  def testGet_WithNonInternalUserAndWhitelistedIP(self):
    self._AddMockInternalData()
    self.SetCurrentUser(None, user_id=None, is_admin=False)
    datastore_hooks.InstallHooks()
    self._SetUpIpWhitelist()
    query = '/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&num_points=3'
    expected = [['revision', 'value']]
    self._CheckGet(query, expected)

  def testGet_WhitelistedIPOnly(self):
    self._AddMockInternalData()
    self.SetCurrentUser(None, user_id=None, is_admin=False)
    datastore_hooks.InstallHooks()
    whitelisted_ip = self._SetUpIpWhitelist()
    query = '/graph_csv?test_path=ChromiumPerf/win7/dromaeo/dom&num_points=3'
    expected = [
        ['revision', 'value'],
        ['47', '94.0'],
        ['48', '96.0'],
        ['49', '98.0']
    ]
    self._CheckGet(query, expected, whitelisted_ip=whitelisted_ip)

  def testGet_NoTestPathGiven_GivesError(self):
    whitelisted_ip = self._SetUpIpWhitelist()
    self.testapp.get(
        '/graph_csv',
        extra_environ={'REMOTE_ADDR': whitelisted_ip},
        status=400)


if __name__ == '__main__':
  unittest.main()
