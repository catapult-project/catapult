# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import json
import os
import unittest


from catapult_build import dev_server
from perf_insights_build import perf_insights_dev_server_config
from tracing_build import tracing_dev_server_config
import webapp2

class DevServerTests(unittest.TestCase):

  def setUp(self):
    self.pds = [
      perf_insights_dev_server_config.PerfInsightsDevServerConfig(),
      tracing_dev_server_config.TracingDevServerConfig(),
    ]

    self.args = dev_server._AddCommandLineArguments(self.pds, [])

  def testStaticDirectoryHandling(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    request = webapp2.Request.blank('/tracing/tests.html')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)

  def testGetURLForAbsFilename(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    class FakeServer(object):
      @property
      def urlbase(self):
          return 'http://localhost:8003'
    app.server = FakeServer()

    cfg = tracing_dev_server_config.TracingDevServerConfig()
    base_html_filename = os.path.join(cfg.project.tracing_src_path,
                                      'base', 'base.html')
    url = app.GetURLForAbsFilename(base_html_filename)
    self.assertEqual(url, 'http://localhost:8003/tracing/base/base.html')

    url = app.GetURLForAbsFilename('/tmp/foo')
    self.assertIsNone(url)

  def testTestDataDirectory(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    request = webapp2.Request.blank('/tracing/test_data/trivial_trace.json')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)

  def testTestDataDirectoryListing(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    request = webapp2.Request.blank('/tracing/test_data/__file_list__')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    assert '/tracing/test_data/trivial_trace.json' in res

  def testSkpDataDirectoryListing(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    request = webapp2.Request.blank('/tracing/skp_data/__file_list__')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    assert '/tracing/skp_data/lthi_cats.skp' in res

  def testTestListingHandler(self):
    app = dev_server.DevServerApp(self.pds, self.args)
    request = webapp2.Request.blank('/tracing/tests')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    self.assertTrue('test_relpaths' in res)
    self.assertTrue(len(res['test_relpaths']) > 0)
