# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.unittest import tab_test_case

class InspectorRuntimeTest(tab_test_case.TabTestCase):
  def testRuntimeEvaluateSimple(self):
    res = self._tab.EvaluateJavaScript('1+1')
    assert res == 2

  def testRuntimeEvaluateThatFails(self):
    self.assertRaises(exceptions.EvaluateException,
                      lambda: self._tab.EvaluateJavaScript('fsdfsdfsf'))

  def testRuntimeEvaluateOfSomethingThatCantJSONize(self):

    def test():
      self._tab.EvaluateJavaScript("""
        var cur = {};
        var root = {next: cur};
        for (var i = 0; i < 1000; i++) {
          next = {};
          cur.next = next;
          cur = next;
        }
        root;""")
    self.assertRaises(exceptions.EvaluateException, test)

  def testRuntimeExecuteOfSomethingThatCantJSONize(self):
    self._tab.ExecuteJavaScript('window')

  def testIFrame(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(self._browser.http_server.UrlOf('host.html'))

    # Access host page.
    self._tab.WaitForJavaScriptExpression(
        "typeof(testVar) != 'undefined'", timeout=5)
    self.assertEquals(self._tab.EvaluateJavaScript('testVar'), 'host')

    # Access parent page using EvaluateJavaScriptInContext.
    self.assertEquals(self._tab.EvaluateJavaScriptInContext('testVar',
        context_id=1), 'host')

    # Access the iframes.
    self.assertEquals(self._tab.EvaluateJavaScriptInContext('testVar',
        context_id=2), 'iframe1')
    self.assertEquals(self._tab.EvaluateJavaScriptInContext('testVar',
        context_id=3), 'iframe2')
    self.assertEquals(self._tab.EvaluateJavaScriptInContext('testVar',
        context_id=4), 'iframe3')

    # Accessing a non-existent iframe throws an exception.
    self.assertRaises(exceptions.EvaluateException,
        lambda: self._tab.EvaluateJavaScriptInContext('1+1', context_id=5))
