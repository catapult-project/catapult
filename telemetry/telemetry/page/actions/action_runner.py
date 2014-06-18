# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.page.actions.javascript_click import ClickElementAction
from telemetry.page.actions.navigate import NavigateAction
from telemetry.page.actions.swipe import SwipeAction
from telemetry.page.actions.tap import TapAction
from telemetry.page.actions.wait import WaitForElementAction
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunner(object):

  def __init__(self, tab):
    self._tab = tab

  # TODO(nednguyen): remove this (or make private) when
  # crbug.com/361809 is marked fixed
  def RunAction(self, action):
    action.WillRunAction(self._tab)
    action.RunAction(self._tab)

  def BeginInteraction(self, label, is_smooth=False, is_responsive=False):
    """Marks the beginning of an interaction record.

    An interaction record is a labeled time period containing
    interaction that developers care about. Each set of metrics
    specified in flags will be calculated for this time period.. The
    End() method in the returned object must be called once to mark
    the end of the timeline.

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      is_smooth: Whether to check for smoothness metrics for this interaction.
      is_responsive: Whether to check for responsiveness metrics for
          this interaction.
    """
    flags = []
    if is_smooth:
      flags.append(tir_module.IS_SMOOTH)
    if is_responsive:
      flags.append(tir_module.IS_RESPONSIVE)

    interaction = Interaction(self._tab, label, flags)
    interaction.Begin()
    return interaction

  def BeginGestureInteraction(
      self, label, is_smooth=False, is_responsive=False):
    """Marks the beginning of a gesture-based interaction record.

    This is similar to normal interaction record, but it will
    auto-narrow the interaction time period to only include the
    synthetic gesture event output by Chrome. This is typically use to
    reduce noise in gesture-based analysis (e.g., analysis for a
    swipe/scroll).

    The interaction record label will be prepended with 'Gesture_'.

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      is_smooth: Whether to check for smoothness metrics for this interaction.
      is_responsive: Whether to check for responsiveness metrics for
          this interaction.
    """
    return self.BeginInteraction('Gesture_' + label, is_smooth, is_responsive)

  def NavigateToPage(self, page, timeout_seconds=None):
    """ Navigate to the given page.

    Args:
      page: page is an instance of page.Page
    """
    if page.is_file:
      target_side_url = self._tab.browser.http_server.UrlOf(page.file_path_url)
    else:
      target_side_url = page.url
    attributes = {
        'url': target_side_url,
        'script_to_evaluate_on_commit': page.script_to_evaluate_on_commit}
    if timeout_seconds:
      attributes['timeout_seconds'] = timeout_seconds
    self.RunAction(NavigateAction(attributes))

  def WaitForNavigate(self, timeout_seconds=60):
    self._tab.WaitForNavigate(timeout_seconds)
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def ExecuteJavaScript(self, statement):
    """Executes a given JavaScript expression. Does not return the result.

    Example: runner.ExecuteJavaScript('var foo = 1;');

    Args:
      statement: The statement to execute (provided as string).

    Raises:
      EvaluationException: The statement failed to execute.
    """
    self._tab.ExecuteJavaScript(statement)

  def EvaluateJavaScript(self, expression):
    """Returns the evaluation result of the given JavaScript expression.

    The evaluation results must be convertible to JSON. If the result
    is not needed, use ExecuteJavaScript instead.

    Example: num = runner.EvaluateJavaScript('document.location.href')

    Args:
      expression: The expression to evaluate (provided as string).

    Raises:
      EvaluationException: The statement expression failed to execute
          or the evaluation result can not be JSON-ized.
    """
    return self._tab.EvaluateJavaScript(expression)

  def Wait(self, seconds):
    """Wait for the number of seconds specified.

    Args:
      seconds: The number of seconds to wait.
    """
    time.sleep(seconds)

  def WaitForJavaScriptCondition(self, condition, timeout=60):
    """Wait for a JavaScript condition to become true.

    Example: runner.WaitForJavaScriptCondition('window.foo == 10');

    Args:
      condition: The JavaScript condition (as string).
      timeout: The timeout in seconds (default to 60).
    """
    self._tab.WaitForJavaScriptExpression(condition, timeout)

  def WaitForElement(self, selector=None, text=None, element_function=None,
                     timeout=60):
    """Wait for an element to appear in the document.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          '(function() { return foo.element; })()'.
      timeout: The timeout in seconds (default to 60).
    """
    self.RunAction(WaitForElementAction(
        selector=selector, text=text, element_function=element_function,
        timeout=timeout))

  def TapElement(self, selector=None, text=None, element_function=None):
    """Tap an element.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          '(function() { return foo.element; })()'.
    """
    self.RunAction(TapAction(
        selector=selector, text=text, element_function=element_function))

  def ClickElement(self, selector=None, text=None, element_function=None):
    """Click an element.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          '(function() { return foo.element; })()'.
    """
    self.RunAction(ClickElementAction(
        selector=selector, text=text, element_function=element_function))

  def SwipePage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                direction='left', distance=100, speed=800):
    """Perform swipe gesture on the page.

    Args:
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      direction: The direction of swipe, either 'left', 'right',
          'up', or 'down'
      distance: The distance to swipe (in pixel).
      speed: The speed of the gesture.
    """
    self.RunAction(SwipeAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, speed=speed))

  def SwipeElement(self, selector=None, text=None, element_function=None,
                   left_start_ratio=0.5, top_start_ratio=0.5,
                   direction='left', distance=100, speed=800):
    """Perform swipe gesture on the element.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          'function() { return foo.element; }'.
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          the element.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          the element.
      direction: The direction of swipe, either 'left', 'right',
          'up', or 'down'
      distance: The distance to swipe (in pixel).
      speed: The speed of the gesture.
    """
    self.RunAction(SwipeAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, speed=speed))

  def ForceGarbageCollection(self):
    """Forces JavaScript garbage collection on the page."""
    self._tab.CollectGarbage()

  def PauseInteractive(self):
    """Pause the page execution and wait for terminal interaction.

    This is typically used for debugging. You can use this to pause
    the page execution and inspect the browser state before
    continuing.
    """
    raw_input("Interacting... Press Enter to continue.")


class Interaction(object):

  def __init__(self, action_runner, label, flags):
    assert action_runner
    assert label
    assert isinstance(flags, list)

    self._action_runner = action_runner
    self._label = label
    self._flags = flags
    self._started = False

  def Begin(self):
    assert not self._started
    self._started = True
    self._action_runner.ExecuteJavaScript('console.time("%s");' %
        tir_module.TimelineInteractionRecord.GetJavaScriptMarker(
            self._label, self._flags))

  def End(self):
    assert self._started
    self._started = False
    self._action_runner.ExecuteJavaScript('console.timeEnd("%s");' %
        tir_module.TimelineInteractionRecord.GetJavaScriptMarker(
            self._label, self._flags))
