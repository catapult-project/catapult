# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import json


from build import tracing_dev_server
import webapp2

class TracingDevServerTests(unittest.TestCase):
  def testStaticDirectoryHandling(self):
    app = tracing_dev_server.CreateApp()
    request = webapp2.Request.blank('/base/tests.html')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)

  def testTestDataDirectory(self):
    app = tracing_dev_server.CreateApp()
    request = webapp2.Request.blank('/test_data/trivial_trace.json')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)

  def testTestDataDirectoryListing(self):
    app = tracing_dev_server.CreateApp()
    request = webapp2.Request.blank('/test_data/__file_list__')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    assert '/test_data/trivial_trace.json' in res

  def testSkpDataDirectoryListing(self):
    app = tracing_dev_server.CreateApp()
    request = webapp2.Request.blank('/skp_data/__file_list__')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    assert '/skp_data/lthi_cats.skp' in res

  def testTestListingHandler(self):
    app = tracing_dev_server.CreateApp()
    request = webapp2.Request.blank('/tr/json/tests')
    response = request.get_response(app)

    self.assertEqual(response.status_int, 200)
    res = json.loads(response.body)
    self.assertTrue('test_relpaths' in res)
    self.assertTrue(len(res['test_relpaths']) > 0)
