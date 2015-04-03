# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry import decorators
from telemetry.internal.actions import page_action
from telemetry.page import action_runner as action_runner_module
from telemetry.timeline import model
from telemetry.unittest_util import tab_test_case
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunnerInteractionTest(tab_test_case.TabTestCase):

  def GetInteractionRecords(self, trace_data):
    timeline_model = model.TimelineModel(trace_data)
    renderer_thread = timeline_model.GetRendererThreadFromTabId(self._tab.id)
    return [
        tir_module.TimelineInteractionRecord.FromAsyncEvent(e)
        for e in renderer_thread.async_slices
        if tir_module.IsTimelineInteractionRecord(e.name)
        ]

  def VerifyIssuingInteractionRecords(self, **interaction_kwargs):
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
    self.Navigate('interaction_enabled_page.html')
    action_runner.Wait(1)
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._browser.platform.tracing_controller.Start(
        options, tracing_category_filter.CreateNoOverheadFilter())
    interaction = action_runner.BeginInteraction('InteractionName',
                                                 **interaction_kwargs)
    interaction.End()
    trace_data = self._browser.platform.tracing_controller.Stop()

    records = self.GetInteractionRecords(trace_data)
    self.assertEqual(
        1, len(records),
        'Failed to issue the interaction record on the tracing timeline.'
        ' Trace data:\n%s' % repr(trace_data._raw_data))
    self.assertEqual('InteractionName', records[0].label)
    for attribute_name in interaction_kwargs:
      self.assertTrue(getattr(records[0], attribute_name))

  # Test disabled for android: crbug.com/437057
  @decorators.Disabled('android', 'chromeos')
  def testIssuingMultipleMeasurementInteractionRecords(self):
    self.VerifyIssuingInteractionRecords(repeatable=True)


class ActionRunnerTest(tab_test_case.TabTestCase):
  def testExecuteJavaScript(self):
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
    self.Navigate('blank.html')
    action_runner.ExecuteJavaScript('var testing = 42;')
    self.assertEqual(42, self._tab.EvaluateJavaScript('testing'))

  def testWaitForNavigate(self):
    self.Navigate('page_with_link.html')
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
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
        'window.setTimeout(function() { window.testing = 101; }, 50);')
    action_runner.Wait(0.1)
    self.assertEqual(101, self._tab.EvaluateJavaScript('window.testing'))

    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 102; }, 100);')
    action_runner.Wait(0.2)
    self.assertEqual(102, self._tab.EvaluateJavaScript('window.testing'))

  def testWaitForJavaScriptCondition(self):
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript('window.testing = 219;')
    action_runner.WaitForJavaScriptCondition(
        'window.testing == 219', timeout_in_seconds=0.1)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() { window.testing = 220; }, 50);')
    action_runner.WaitForJavaScriptCondition(
        'window.testing == 220', timeout_in_seconds=0.1)
    self.assertEqual(220, self._tab.EvaluateJavaScript('window.testing'))

  def testWaitForElement(self):
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript(
        '(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test1";'
        '  el.textContent = "foo";'
        '  document.body.appendChild(el);'
        '})()')
    action_runner.WaitForElement('#test1', timeout_in_seconds=0.1)
    action_runner.WaitForElement(text='foo', timeout_in_seconds=0.1)
    action_runner.WaitForElement(
        element_function='document.getElementById("test1")')
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test2";'
        '  document.body.appendChild(el);'
        '}, 50)')
    action_runner.WaitForElement('#test2', timeout_in_seconds=0.1)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  document.getElementById("test2").textContent = "bar";'
        '}, 50)')
    action_runner.WaitForElement(text='bar', timeout_in_seconds=0.1)
    action_runner.ExecuteJavaScript(
        'window.setTimeout(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test3";'
        '  document.body.appendChild(el);'
        '}, 50)')
    action_runner.WaitForElement(
        element_function='document.getElementById("test3")')

  def testWaitForElementWithWrongText(self):
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)
    self.Navigate('blank.html')

    action_runner.ExecuteJavaScript(
        '(function() {'
        '  var el = document.createElement("div");'
        '  el.id = "test1";'
        '  el.textContent = "foo";'
        '  document.body.appendChild(el);'
        '})()')
    action_runner.WaitForElement('#test1', timeout_in_seconds=0.2)
    def WaitForElement():
      action_runner.WaitForElement(text='oo', timeout_in_seconds=0.2)
    self.assertRaises(exceptions.TimeoutException, WaitForElement)

  def testClickElement(self):
    self.Navigate('page_with_clickables.html')
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)

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

  @decorators.Disabled('android', 'debug') # crbug.com/437068
  def testTapElement(self):
    self.Navigate('page_with_clickables.html')
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)

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

  @decorators.Disabled('android') # crbug.com/437065.
  def testScroll(self):
    if not page_action.IsGestureSourceTypeSupported(
        self._tab, 'touch'):
      return

    self.Navigate('page_with_swipeables.html')
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)

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

  @decorators.Disabled('android') # crbug.com/437065.
  def testSwipe(self):
    if not page_action.IsGestureSourceTypeSupported(
        self._tab, 'touch'):
      return

    self.Navigate('page_with_swipeables.html')
    action_runner = action_runner_module.ActionRunner(self._tab,
                                                      skip_waits=True)

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
