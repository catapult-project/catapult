# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.page.actions.javascript_click import ClickElementAction
from telemetry.page.actions.loop import LoopAction
from telemetry.page.actions.navigate import NavigateAction
from telemetry.page.actions.pinch import PinchAction
from telemetry.page.actions.play import PlayAction
from telemetry.page.actions.repaint_continuously import (
    RepaintContinuouslyAction)
from telemetry.page.actions.scroll import ScrollAction
from telemetry.page.actions.scroll_bounce import ScrollBounceAction
from telemetry.page.actions.seek import SeekAction
from telemetry.page.actions.swipe import SwipeAction
from telemetry.page.actions.tap import TapAction
from telemetry.page.actions.wait import WaitForElementAction
from telemetry.web_perf import timeline_interaction_record


class ActionRunner(object):

  def __init__(self, tab, skip_waits=False):
    self._tab = tab
    self._skip_waits = skip_waits

  def _RunAction(self, action):
    action.WillRunAction(self._tab)
    action.RunAction(self._tab)

  def BeginInteraction(self, label, is_fast=False, is_smooth=False,
                       is_responsive=False, repeatable=False):
    """Marks the beginning of an interaction record.

    An interaction record is a labeled time period containing
    interaction that developers care about. Each set of metrics
    specified in flags will be calculated for this time period.. The
    End() method in the returned object must be called once to mark
    the end of the timeline.

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      is_fast: Whether to measure how fast the browser completes necessary work
          for this interaction record. See fast_metric.py for details.
      is_smooth: Whether to check for smoothness metrics for this interaction.
      is_responsive: Whether to check for responsiveness metrics for
          this interaction.
      repeatable: Whether other interactions may use the same logical name
          as this interaction. All interactions with the same logical name must
          have the same flags.
    """
    flags = []
    if is_fast:
      flags.append(timeline_interaction_record.IS_FAST)
    if is_smooth:
      flags.append(timeline_interaction_record.IS_SMOOTH)
    if is_responsive:
      flags.append(timeline_interaction_record.IS_RESPONSIVE)
    if repeatable:
      flags.append(timeline_interaction_record.REPEATABLE)

    interaction = Interaction(self._tab, label, flags)
    interaction.Begin()
    return interaction

  def BeginGestureInteraction(self, label, is_fast=False, is_smooth=False,
                              is_responsive=False, repeatable=False):
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
      is_fast: Whether to measure how fast the browser completes necessary work
          for this interaction record. See fast_metric.py for details.
      is_smooth: Whether to check for smoothness metrics for this interaction.
      is_responsive: Whether to check for responsiveness metrics for
          this interaction.
      repeatable: Whether other interactions may use the same logical name
          as this interaction. All interactions with the same logical name must
          have the same flags.
    """
    return self.BeginInteraction('Gesture_' + label, is_fast, is_smooth,
                                 is_responsive, repeatable)

  def NavigateToPage(self, page, timeout_in_seconds=60):
    """Navigate to the given page.

    Args:
      page: page is an instance of page.Page
      timeout_in_seconds: The timeout in seconds (default to 60).
    """
    if page.is_file:
      target_side_url = self._tab.browser.http_server.UrlOf(page.file_path_url)
    else:
      target_side_url = page.url
    self._RunAction(NavigateAction(
        url=target_side_url,
        script_to_evaluate_on_commit=page.script_to_evaluate_on_commit,
        timeout_in_seconds=timeout_in_seconds))

  def WaitForNavigate(self, timeout_in_seconds_seconds=60):
    self._tab.WaitForNavigate(timeout_in_seconds_seconds)
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def ReloadPage(self):
    """Reloads the page."""
    self._tab.ExecuteJavaScript('window.location.reload()')
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
    if not self._skip_waits:
      time.sleep(seconds)

  def WaitForJavaScriptCondition(self, condition, timeout_in_seconds=60):
    """Wait for a JavaScript condition to become true.

    Example: runner.WaitForJavaScriptCondition('window.foo == 10');

    Args:
      condition: The JavaScript condition (as string).
      timeout_in_seconds: The timeout in seconds (default to 60).
    """
    self._tab.WaitForJavaScriptExpression(condition, timeout_in_seconds)

  def WaitForElement(self, selector=None, text=None, element_function=None,
                     timeout_in_seconds=60):
    """Wait for an element to appear in the document.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          '(function() { return foo.element; })()'.
      timeout_in_seconds: The timeout in seconds (default to 60).
    """
    self._RunAction(WaitForElementAction(
        selector=selector, text=text, element_function=element_function,
        timeout_in_seconds=timeout_in_seconds))

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
    self._RunAction(TapAction(
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
    self._RunAction(ClickElementAction(
        selector=selector, text=text, element_function=element_function))

  def PinchPage(self, left_anchor_ratio=0.5, top_anchor_ratio=0.5,
                scale_factor=None, speed_in_pixels_per_second=800):
    """Perform the pinch gesture on the page.

    It computes the pinch gesture automatically based on the anchor
    coordinate and the scale factor. The scale factor is the ratio of
    of the final span and the initial span of the gesture.

    Args:
      left_anchor_ratio: The horizontal pinch anchor coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_anchor_ratio: The vertical pinch anchor coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      scale_factor: The ratio of the final span to the initial span.
          The default scale factor is
          3.0 / (window.outerWidth/window.innerWidth).
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(PinchAction(
        left_anchor_ratio=left_anchor_ratio, top_anchor_ratio=top_anchor_ratio,
        scale_factor=scale_factor,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def PinchElement(self, selector=None, text=None, element_function=None,
                   left_anchor_ratio=0.5, top_anchor_ratio=0.5,
                   scale_factor=None, speed_in_pixels_per_second=800):
    """Perform the pinch gesture on an element.

    It computes the pinch gesture automatically based on the anchor
    coordinate and the scale factor. The scale factor is the ratio of
    of the final span and the initial span of the gesture.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          'function() { return foo.element; }'.
      left_anchor_ratio: The horizontal pinch anchor coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          the element.
      top_anchor_ratio: The vertical pinch anchor coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          the element.
      scale_factor: The ratio of the final span to the initial span.
          The default scale factor is
          3.0 / (window.outerWidth/window.innerWidth).
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(PinchAction(
        selector=selector, text=text, element_function=element_function,
        left_anchor_ratio=left_anchor_ratio, top_anchor_ratio=top_anchor_ratio,
        scale_factor=scale_factor,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def ScrollPage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                 direction='down', distance=None, distance_expr=None,
                 speed_in_pixels_per_second=800, use_touch=False):
    """Perform scroll gesture on the page.

    You may specify distance or distance_expr, but not both. If
    neither is specified, the default scroll distance is variable
    depending on direction (see scroll.js for full implementation).

    Args:
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      direction: The direction of scroll, either 'left', 'right',
          'up', or 'down'
      distance: The distance to scroll (in pixel).
      distance_expr: A JavaScript expression (as string) that can be
          evaluated to compute scroll distance. Example:
          'window.scrollTop' or '(function() { return crazyMath(); })()'.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
      use_touch: Whether scrolling should be done with touch input.
    """
    self._RunAction(ScrollAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, distance_expr=distance_expr,
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        use_touch=use_touch))

  def ScrollElement(self, selector=None, text=None, element_function=None,
                    left_start_ratio=0.5, top_start_ratio=0.5,
                    direction='down', distance=None, distance_expr=None,
                    speed_in_pixels_per_second=800, use_touch=False):
    """Perform scroll gesture on the element.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    You may specify distance or distance_expr, but not both. If
    neither is specified, the default scroll distance is variable
    depending on direction (see scroll.js for full implementation).

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
      direction: The direction of scroll, either 'left', 'right',
          'up', or 'down'
      distance: The distance to scroll (in pixel).
      distance_expr: A JavaScript expression (as string) that can be
          evaluated to compute scroll distance. Example:
          'window.scrollTop' or '(function() { return crazyMath(); })()'.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
      use_touch: Whether scrolling should be done with touch input.
    """
    self._RunAction(ScrollAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, distance_expr=distance_expr,
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        use_touch=use_touch))

  def ScrollBouncePage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                       direction='down', distance=100,
                       overscroll=10, repeat_count=10,
                       speed_in_pixels_per_second=400):
    """Perform scroll bounce gesture on the page.

    This gesture scrolls the page by the number of pixels specified in
    distance, in the given direction, followed by a scroll by
    (distance + overscroll) pixels in the opposite direction.
    The above gesture is repeated repeat_count times.

    Args:
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      direction: The direction of scroll, either 'left', 'right',
          'up', or 'down'
      distance: The distance to scroll (in pixel).
      overscroll: The number of additional pixels to scroll back, in
          addition to the givendistance.
      repeat_count: How often we want to repeat the full gesture.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(ScrollBounceAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance,
        overscroll=overscroll, repeat_count=repeat_count,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def ScrollBounceElement(self, selector=None, text=None, element_function=None,
                          left_start_ratio=0.5, top_start_ratio=0.5,
                          direction='down', distance=100,
                          overscroll=10, repeat_count=10,
                          speed_in_pixels_per_second=400):
    """Perform scroll bounce gesture on the element.

    This gesture scrolls on the element by the number of pixels specified in
    distance, in the given direction, followed by a scroll by
    (distance + overscroll) pixels in the opposite direction.
    The above gesture is repeated repeat_count times.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          'function() { return foo.element; }'.
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      direction: The direction of scroll, either 'left', 'right',
          'up', or 'down'
      distance: The distance to scroll (in pixel).
      overscroll: The number of additional pixels to scroll back, in
          addition to the givendistance.
      repeat_count: How often we want to repeat the full gesture.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(ScrollBounceAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance,
        overscroll=overscroll, repeat_count=repeat_count,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def SwipePage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                direction='left', distance=100, speed_in_pixels_per_second=800):
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
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(SwipeAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def SwipeElement(self, selector=None, text=None, element_function=None,
                   left_start_ratio=0.5, top_start_ratio=0.5,
                   direction='left', distance=100,
                   speed_in_pixels_per_second=800):
    """Perform swipe gesture on the element.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

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
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(SwipeAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def PlayMedia(self, selector=None,
                playing_event_timeout_in_seconds=0,
                ended_event_timeout_in_seconds=0):
    """Invokes the "play" action on media elements (such as video).

    Args:
      selector: A CSS selector describing the element. If none is
          specified, play the first media element on the page. If the
          selector matches more than 1 media element, all of them will
          be played.
      playing_event_timeout_in_seconds: Maximum waiting time for the "playing"
          event (dispatched when the media begins to play) to be fired.
          0 means do not wait.
      ended_event_timeout_in_seconds: Maximum waiting time for the "ended"
          event (dispatched when playback completes) to be fired.
          0 means do not wait.

    Raises:
      TimeoutException: If the maximum waiting time is exceeded.
    """
    self._RunAction(PlayAction(
        selector=selector,
        playing_event_timeout_in_seconds=playing_event_timeout_in_seconds,
        ended_event_timeout_in_seconds=ended_event_timeout_in_seconds))

  def SeekMedia(self, seconds, selector=None, timeout_in_seconds=0,
                log_time=True, label=''):
    """Performs a seek action on media elements (such as video).

    Args:
      seconds: The media time to seek to.
      selector: A CSS selector describing the element. If none is
          specified, seek the first media element on the page. If the
          selector matches more than 1 media element, all of them will
          be seeked.
      timeout_in_seconds: Maximum waiting time for the "seeked" event
          (dispatched when the seeked operation completes) to be
          fired.  0 means do not wait.
      log_time: Whether to log the seek time for the perf
          measurement. Useful when performing multiple seek.
      label: A suffix string to name the seek perf measurement.

    Raises:
      TimeoutException: If the maximum waiting time is exceeded.
    """
    self._RunAction(SeekAction(
        seconds=seconds, selector=selector,
        timeout_in_seconds=timeout_in_seconds,
        log_time=log_time, label=label))

  def LoopMedia(self, loop_count, selector=None, timeout_in_seconds=None):
    """Loops a media playback.

    Args:
      loop_count: The number of times to loop the playback.
      selector: A CSS selector describing the element. If none is
          specified, loop the first media element on the page. If the
          selector matches more than 1 media element, all of them will
          be looped.
      timeout_in_seconds: Maximum waiting time for the looped playback to
          complete. 0 means do not wait. None (the default) means to
          wait loop_count * 60 seconds.

    Raises:
      TimeoutException: If the maximum waiting time is exceeded.
    """
    self._RunAction(LoopAction(
        loop_count=loop_count, selector=selector,
        timeout_in_seconds=timeout_in_seconds))

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

  def RepaintContinuously(self, seconds):
    """Continuously repaints the visible content.

    It does this by requesting animation frames until the given number
    of seconds have elapsed AND at least three RAFs have been
    fired. Times out after max(60, self.seconds), if less than three
    RAFs were fired."""
    self._RunAction(RepaintContinuouslyAction(seconds=seconds))

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
        timeline_interaction_record.GetJavaScriptMarker(
            self._label, self._flags))

  def End(self):
    assert self._started
    self._started = False
    self._action_runner.ExecuteJavaScript('console.timeEnd("%s");' %
        timeline_interaction_record.GetJavaScriptMarker(
            self._label, self._flags))
