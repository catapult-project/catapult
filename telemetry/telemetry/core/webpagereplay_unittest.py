# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import webpagereplay


# pylint: disable=W0212
class ParseLogFilePortsTest(unittest.TestCase):
  def testEmptyLinesGivesEmptyDict(self):
    log_lines = iter([])
    self.assertEqual(
      {},
      webpagereplay.ReplayServer._ParseLogFilePorts(log_lines))

  def testSingleMatchGivesSingleElementDict(self):
    log_lines = iter([
        'extra stuff',
        '2014-09-27 17:04:27,11 WARNING HTTP server started on 127.0.0.1:5167',
        'extra stuff',
        ])
    self.assertEqual(
        {'http': 5167},
        webpagereplay.ReplayServer._ParseLogFilePorts(log_lines))

  def testUnknownProtocolSkipped(self):
    log_lines = iter([
        '2014-09-27 17:04:27,11 WARNING FOO server started on 127.0.0.1:1111',
        '2014-09-27 17:04:27,12 WARNING HTTP server started on 127.0.0.1:5167',
        ])
    self.assertEqual(
        {'http': 5167},
        webpagereplay.ReplayServer._ParseLogFilePorts(log_lines))

  def testTypicalLogLinesGiveFullDict(self):
    log_lines = iter([
        'extra',
        '2014-09-27 17:04:27,11 WARNING DNS server started on 127.0.0.1:2345',
        '2014-09-27 17:04:27,12 WARNING HTTP server started on 127.0.0.1:3456',
        '2014-09-27 17:04:27,13 WARNING HTTPS server started on 127.0.0.1:4567',
        ])
    self.assertEqual(
        {'dns': 2345, 'http': 3456, 'https': 4567},
        webpagereplay.ReplayServer._ParseLogFilePorts(log_lines))
