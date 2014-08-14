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
    starting_contexts = self._tab.EnableAllContexts()

    self.Navigate('host.html')

    # Access host page.
    test_defined_js = "typeof(testVar) != 'undefined'"
    self._tab.WaitForJavaScriptExpression(test_defined_js, timeout=10)

    expected_contexts = 4 + starting_contexts

    util.WaitFor(lambda: self._tab.EnableAllContexts() == expected_contexts,
                 timeout=10)

    self.assertEquals(self._tab.EvaluateJavaScript('testVar'), 'host')

    def TestVarReady(context_id):
      """Returns True if the context and testVar are both ready."""
      try:
        return self._tab.EvaluateJavaScriptInContext(test_defined_js,
                                                     context_id)
      except exceptions.EvaluateException:
        # This happens when the context is not ready.
        return False

    def TestVar(context_id):
      """Waits for testVar and the context to be ready, then returns the value
      of testVar."""
      util.WaitFor(lambda: TestVarReady(context_id), timeout=10)
      return self._tab.EvaluateJavaScriptInContext('testVar', context_id)

    # Access parent page using EvaluateJavaScriptInContext.
    self.assertEquals(TestVar(context_id=starting_contexts+1), 'host')

    # Access the iframes.
    self.assertEquals(TestVar(context_id=starting_contexts+2), 'iframe1')
    self.assertTrue(TestVar(context_id=starting_contexts+3) in ['iframe2',
                                                                'iframe3'])
    self.assertTrue(TestVar(context_id=starting_contexts+4) in ['iframe2',
                                                                'iframe3'])

    # Accessing a non-existent iframe throws an exception.
    self.assertRaises(exceptions.EvaluateException,
        lambda: self._tab.EvaluateJavaScriptInContext(
          '1+1', context_id=starting_contexts+5))
