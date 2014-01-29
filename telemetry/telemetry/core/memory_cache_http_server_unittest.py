# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.core import util
from telemetry.unittest import options_for_unittests


class MemoryCacheHTTPServerTest(unittest.TestCase):

  def setUp(self):
    self.test_file = 'bear.webm'
    test_file_path = os.path.join(util.GetUnittestDataDir(), self.test_file)
    self.test_file_size = os.stat(test_file_path).st_size

  def testBasicHostingAndRangeRequests(self):
    options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(options)
    with browser_to_create.Create() as b:
      b.SetHTTPServerDirectories(util.GetUnittestDataDir())
      t = b.tabs[0]
      t.Navigate(b.http_server.UrlOf('/blank.html'))
      t.WaitForDocumentReadyStateToBeComplete()
      x = t.EvaluateJavaScript('document.body.innerHTML')
      x = x.strip()

      # Test basic html hosting.
      self.assertEquals(x, 'Hello world')

      file_size = self.test_file_size
      last_byte = file_size - 1
      # Test byte range request: no end byte.
      self.CheckContentHeaders(b, t, '0-', '0-%d' % last_byte, file_size)

      # Test byte range request: greater than zero start byte.
      self.CheckContentHeaders(b, t, '100-', '100-%d' % last_byte,
                               file_size - 100)

      # Test byte range request: explicit byte range.
      self.CheckContentHeaders(b, t, '2-500', '2-500', '499')

      # Test byte range request: no start byte.
      self.CheckContentHeaders(b, t, '-228',
                               '%d-%d' % (file_size - 228, last_byte),
                               '228')

      # Test byte range request: end byte less than start byte.
      self.CheckContentHeaders(b, t, '100-5', '100-%d' % last_byte,
                               file_size - 100)

  def CheckContentHeaders(self, browser, tab, content_range_request,
                          content_range_response, content_lenght_response):
    tab.ExecuteJavaScript("""
        var loaded = false;
        var xmlhttp = new XMLHttpRequest();
        xmlhttp.onload = function(e) {
          loaded = true;
        };
        // Avoid cached content by appending unique URL param.
        xmlhttp.open('GET', "%s?t=" + Date.now(), true);
        xmlhttp.setRequestHeader('Range', 'bytes=%s');
        xmlhttp.send();
    """ % (browser.http_server.UrlOf('/%s' % self.test_file),
           content_range_request))
    tab.WaitForJavaScriptExpression('loaded', 5)
    content_range = tab.EvaluateJavaScript(
        'xmlhttp.getResponseHeader("Content-Range");')
    content_range_response = 'bytes %s/%d' % (
        content_range_response, self.test_file_size)
    self.assertEquals(content_range, content_range_response)
    content_length = tab.EvaluateJavaScript(
        'xmlhttp.getResponseHeader("Content-Length");')
    self.assertEquals(content_length, str(content_lenght_response))
