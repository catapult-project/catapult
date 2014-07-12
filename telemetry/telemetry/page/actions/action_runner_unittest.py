# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import benchmark
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core.backends.chrome import tracing_backend
from telemetry.timeline import model
from telemetry.page.actions import action_runner as action_runner_module
from telemetry.page.actions import page_action
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
    self.assertEqual('TestInteraction', records[0].label)
    self.assertTrue(records[0].is_smooth)

  def testExecuteJavaScript(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('blank.html')
    action_runner.ExecuteJavaScript('var testing = 42;')
    self.assertEqual(42, self._tab.EvaluateJavaScript('testing'))

  def testWaitForNavigate(self):
    self.Navigate('page_with_link.html')
    action_runner = action_runner_module.ActionRunner(self._tab)
    action_runner.ClickElement('#clickme')
    action_runner.WaitForNavigate()

    self.assertTrue(self._tab.EvaluateJavaScript(
        'document.readyState == "interactive" || '
        'document.readyState == "complete"'))
    self.assertEqual(
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
        'window.testing == 219', timeout_in_seconds=1)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 220; }, 1000);')
    action_runner.WaitForJavaScriptCondition(
        'window.testing == 220', timeout_in_seconds=2)
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
    action_runner.WaitForElement('#test1', timeout_in_seconds=1)
    action_runner.WaitForElement(text='foo', timeout_in_seconds=1)
    action_runner.WaitForElement(
        element_function='document.getElementById("test1")')
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test2";'
        '  document.body.appendChild(el);'
        '}, 500)')
    action_runner.WaitForElement('#test2', timeout_in_seconds=2)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  document.getElementById("test2").textContent = "bar";'
        '}, 500)')
    action_runner.WaitForElement(text='bar', timeout_in_seconds=2)
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
    action_runner.WaitForElement('#test1', timeout_in_seconds=1)
    def WaitForElement():
      action_runner.WaitForElement(text='oo', timeout_in_seconds=1)
    self.assertRaises(util.TimeoutException, WaitForElement)

  def testClickElement(self):
    self.Navigate('page_with_clickables.html')
    action_runner = action_runner_module.ActionRunner(self._tab)

    action_runner.ExecuteJavaScript('valueSettableByTest = 1;')
    action_runner.ClickElement('#test')
    self.assertEqual(1, action_runner.EvaluateJavaScript('valueToTest'))

    action_runner.ExecuteJavaScript('valueSettableByTest = 2;')
    action_runner.ClickElement(text='Click/tap me')
    self.assertEqual(2, action_runner.EvaluateJavaScript('valueToTest'))

    action_runner.ExecuteJavaScript('valueSettableByTest = 3;')
    action_runner.ClickElement(
        element_function='document.body.firstElementChild;')
    self.assertEqual(3, action_runner.EvaluateJavaScript('valueToTest'))

    def WillFail():
      action_runner.ClickElement('#notfound')
    self.assertRaises(exceptions.EvaluateException, WillFail)

  @benchmark.Disabled('debug')
  def testTapElement(self):
    self.Navigate('page_with_clickables.html')
    action_runner = action_runner_module.ActionRunner(self._tab)

    action_runner.ExecuteJavaScript('valueSettableByTest = 1;')
    action_runner.TapElement('#test')
    self.assertEqual(1, action_runner.EvaluateJavaScript('valueToTest'))

    action_runner.ExecuteJavaScript('valueSettableByTest = 2;')
    action_runner.TapElement(text='Click/tap me')
    self.assertEqual(2, action_runner.EvaluateJavaScript('valueToTest'))

    action_runner.ExecuteJavaScript('valueSettableByTest = 3;')
    action_runner.TapElement(
        element_function='document.body.firstElementChild')
    self.assertEqual(3, action_runner.EvaluateJavaScript('valueToTest'))

    def WillFail():
      action_runner.TapElement('#notfound')
    self.assertRaises(exceptions.EvaluateException, WillFail)

  def testScroll(self):
    if not page_action.IsGestureSourceTypeSupported(
        self._tab, 'touch'):
      return

    self.Navigate('page_with_swipeables.html')
    action_runner = action_runner_module.ActionRunner(self._tab)

    action_runner.ScrollElement(
        selector='#left-right', direction='right', left_start_ratio=0.9)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.querySelector("#left-right").scrollLeft') > 75)
    action_runner.ScrollElement(
        selector='#top-bottom', direction='down', top_start_ratio=0.9)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.querySelector("#top-bottom").scrollTop') > 75)

    action_runner.ScrollPage(direction='right', left_start_ratio=0.9,
                             distance=100)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.body.scrollLeft') > 75)

  def testSwipe(self):
    if not page_action.IsGestureSourceTypeSupported(
        self._tab, 'touch'):
      return

    self.Navigate('page_with_swipeables.html')
    action_runner = action_runner_module.ActionRunner(self._tab)

    action_runner.SwipeElement(
        selector='#left-right', direction='left', left_start_ratio=0.9)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.querySelector("#left-right").scrollLeft') > 75)
    action_runner.SwipeElement(
        selector='#top-bottom', direction='up', top_start_ratio=0.9)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.querySelector("#top-bottom").scrollTop') > 75)

    action_runner.SwipePage(direction='left', left_start_ratio=0.9)
    self.assertTrue(action_runner.EvaluateJavaScript(
        'document.body.scrollLeft') > 75)
