# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.core.backends.chrome import tracing_backend
from telemetry.core.timeline import model
from telemetry.page.actions import action_runner as action_runner_module
from telemetry.page.actions import page_action
# pylint: disable=W0401,W0614
from telemetry.page.actions.all_page_actions import *
from telemetry.unittest import tab_test_case
from telemetry.unittest import tab_test_case
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunnerTest(tab_test_case.TabTestCase):
  def testIssuingInteractionRecord(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('interaction_enabled_page.html')
    action_runner.Wait(1)
    self._browser.StartTracing(tracing_backend.DEFAULT_TRACE_CATEGORIES)
    interaction = action_runner.BeginInteraction(
        'TestInteraction', is_smooth=True)
    interaction.End()
    trace_data = self._browser.StopTracing()
    timeline_model = model.TimelineModel(trace_data)

    records = []
    renderer_thread = timeline_model.GetRendererThreadFromTabId(self._tab.id)
    for event in renderer_thread.async_slices:
      if not tir_module.IsTimelineInteractionRecord(event.name):
        continue
      records.append(tir_module.TimelineInteractionRecord.FromAsyncEvent(event))
    self.assertEqual(1, len(records),
                     'Fail to issue the interaction record on tracing timeline.'
                     ' Trace data:\n%s' % repr(trace_data.EventData()))
    self.assertEqual('TestInteraction', records[0].logical_name)
    self.assertTrue(records[0].is_smooth)

  def testExecuteJavaScript(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')
    action_runner.ExecuteJavaScript('var testing = 42;')
    self.assertEqual(42, self._tab.EvaluateJavaScript('testing'))

  def testWaitForNavigate(self):
    self.Navigate('page_with_link.html')
    action_runner = action_runner_module.ActionRunner(self._tab)
    action_runner.RunAction(ClickElementAction({'xpath': 'id("clickme")'}))
    action_runner.WaitForNavigate()

    self.assertTrue(self._tab.EvaluateJavaScript(
        'document.readyState == "interactive" || '
        'document.readyState == "complete"'))
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testWait(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 101; }, 1000);')
    action_runner.Wait(2)
    self.assertEqual(101, self._tab.EvaluateJavaScript('window.testing'))

    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 102; }, 2000);')
    action_runner.Wait(3)
    self.assertEqual(102, self._tab.EvaluateJavaScript('window.testing'))

  def testWaitForJavaScriptCondition(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript('window.testing = 219;')
    action_runner.WaitForJavaScriptCondition(
        'window.testing == 219', timeout=1)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 220; }, 1000);')
    action_runner.WaitForJavaScriptCondition(
        'window.testing == 220', timeout=2)
    self.assertEqual(220, self._tab.EvaluateJavaScript('window.testing'))

  def testWaitForElement(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript(
        '(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test1";'
        '  el.textContent = "foo";'
        '  document.body.appendChild(el);'
        '})()')
    action_runner.WaitForElement('#test1', timeout=1)
    action_runner.WaitForElement(text='foo', timeout=1)
    action_runner.WaitForElement(
        element_function='document.getElementById("test1")')
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test2";'
        '  document.body.appendChild(el);'
        '}, 500)')
    action_runner.WaitForElement('#test2', timeout=2)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  document.getElementById("test2").textContent = "bar";'
        '}, 500)')
    action_runner.WaitForElement(text='bar', timeout=2)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test3";'
        '  document.body.appendChild(el);'
        '}, 500)')
    action_runner.WaitForElement(
        element_function='document.getElementById("test3")')

  def testWaitForElementWithWrongText(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript(
        '(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test1";'
        '  el.textContent = "foo";'
        '  document.body.appendChild(el);'
        '})()')
    action_runner.WaitForElement('#test1', timeout=1)
    def WaitForElement():
      action_runner.WaitForElement(text='oo', timeout=1)
    self.assertRaises(util.TimeoutException, WaitForElement)

  def testWaitForElementWithConflictingParams(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    def WaitForElement1():
      action_runner.WaitForElement(selector='div', text='foo', timeout=1)
    self.assertRaises(page_action.PageActionFailed, WaitForElement1)

    def WaitForElement2():
      action_runner.WaitForElement(selector='div', element_function='foo',
                                   timeout=1)
    self.assertRaises(page_action.PageActionFailed, WaitForElement2)

    def WaitForElement3():
      action_runner.WaitForElement(text='foo', element_function='', timeout=1)
    self.assertRaises(page_action.PageActionFailed, WaitForElement3)
