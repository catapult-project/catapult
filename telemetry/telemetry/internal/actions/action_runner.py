# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import division
from __future__ import absolute_import
import logging
import time
import six
import six.moves.urllib.parse # pylint: disable=import-error,wrong-import-order
from six.moves import input # pylint: disable=redefined-builtin

from telemetry.core import exceptions
from telemetry.internal.actions import page_action
from telemetry.internal.actions.drag import DragAction
from telemetry.internal.actions.javascript_click import ClickElementAction
from telemetry.internal.actions.key_event import KeyPressAction
from telemetry.internal.actions.load_media import LoadMediaAction
from telemetry.internal.actions.mouse_click import MouseClickAction
from telemetry.internal.actions.navigate import NavigateAction
from telemetry.internal.actions.page_action import GESTURE_SOURCE_DEFAULT
from telemetry.internal.actions.page_action import INPUT_EVENT_PATTERN_DEFAULT
from telemetry.internal.actions.page_action import SUPPORTED_GESTURE_SOURCES
from telemetry.internal.actions.pinch import PinchAction
from telemetry.internal.actions.play import PlayAction
from telemetry.internal.actions.repaint_continuously import (
    RepaintContinuouslyAction)
from telemetry.internal.actions.repeatable_scroll import RepeatableScrollAction
from telemetry.internal.actions.scroll import ScrollAction
from telemetry.internal.actions.scroll_bounce import ScrollBounceAction
from telemetry.internal.actions.scroll_to_element import ScrollToElementAction
from telemetry.internal.actions.seek import SeekAction
from telemetry.internal.actions.swipe import SwipeAction
from telemetry.internal.actions.tap import TapAction
from telemetry.internal.actions.wait import WaitForElementAction
from telemetry.web_perf import timeline_interaction_record

from py_trace_event import trace_event

import py_utils


# Time to wait in seconds before requesting a memory dump in deterministic
# mode, thus allowing metric values to stabilize a bit.
_MEMORY_DUMP_WAIT_TIME = 3

# Time to wait in seconds after forcing garbage collection to allow its
# effects to propagate. Experimentally determined on an Android One device
# that Java Heap garbage collection can take ~5 seconds to complete.
_GARBAGE_COLLECTION_PROPAGATION_TIME = 6

# Timeout for websocket communication when using inspector
_DEFAULT_WEBSOCKET_TIMEOUT = 60

ActionRunnerBase = six.with_metaclass(trace_event.TracedMetaClass, object)

class ActionRunner(ActionRunnerBase):

  if six.PY2:
    __metaclass__ = trace_event.TracedMetaClass

  def __init__(self, tab, skip_waits=False):
    self._tab = tab
    self._skip_waits = skip_waits

  @property
  def tab(self):
    """Returns the tab on which actions are performed."""
    return self._tab

  def _RunAction(self, action):
    logging.info("START Page Action: %s", action)
    action.WillRunAction(self._tab)
    action.RunAction(self._tab)
    logging.info("DONE Page Action: %s", action.__class__.__name__)

  def CreateInteraction(self, label, repeatable=False):
    """ Create an action.Interaction object that issues interaction record.

    An interaction record is a labeled time period containing
    interaction that developers care about. Each set of metrics
    specified in flags will be calculated for this time period.

    To mark the start of interaction record, call Begin() method on the returned
    object. To mark the finish of interaction record, call End() method on
    it. Or better yet, use the with statement to create an
    interaction record that covers the actions in the with block.

    e.g:
      with action_runner.CreateInteraction('Animation-1'):
        action_runner.TapElement(...)
        action_runner.WaitForJavaScriptCondition(...)

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      repeatable: Whether other interactions may use the same logical name
          as this interaction. All interactions with the same logical name must
          have the same flags.

    Returns:
      An instance of action_runner.Interaction
    """
    flags = []
    if repeatable:
      flags.append(timeline_interaction_record.REPEATABLE)

    return Interaction(self, label, flags)

  def CreateGestureInteraction(self, label, repeatable=False):
    """ Create an action.Interaction object that issues gesture-based
    interaction record.

    This is similar to normal interaction record, but it will
    auto-narrow the interaction time period to only include the
    synthetic gesture event output by Chrome. This is typically use to
    reduce noise in gesture-based analysis (e.g., analysis for a
    swipe/scroll).

    The interaction record label will be prepended with 'Gesture_'.

    e.g:
      with action_runner.CreateGestureInteraction('Scroll-1'):
        action_runner.ScrollPage()

    Args:
      label: A label for this particular interaction. This can be any
          user-defined string, but must not contain '/'.
      repeatable: Whether other interactions may use the same logical name
          as this interaction. All interactions with the same logical name must
          have the same flags.

    Returns:
      An instance of action_runner.Interaction
    """
    return self.CreateInteraction('Gesture_' + label, repeatable)

  def WaitForNetworkQuiescence(self, timeout_in_seconds=10):
    """ Wait for network quiesence on the page.
    Args:
      timeout_in_seconds: maximum amount of time (seconds) to wait for network
        quiesence before raising exception.

    Raises:
      py_utils.TimeoutException when the timeout is reached but the page's
        network is not quiet.
    """

    py_utils.WaitFor(self.tab.HasReachedQuiescence, timeout_in_seconds)

  def MeasureMemory(self, deterministic_mode=False, timeout_in_seconds=60):
    """Add a memory measurement to the trace being recorded.

    Behaves as a no-op if tracing is not enabled.

    Args:
      deterministic_mode: A boolean indicating whether to attempt or not to
          control the environment (force GCs, clear caches) before making the
          measurement in an attempt to obtain more deterministic results.
      timeout_in_seconds: maximum amount of time (seconds) to wait for a
          garbage collection to complete.

    Returns:
      GUID of the generated dump if one was triggered, None otherwise.
    """
    if not self.tab.browser.platform.tracing_controller.is_tracing_running:
      logging.warning('Tracing is off. No memory dumps are being recorded.')
      return None
    if deterministic_mode:
      self.Wait(_MEMORY_DUMP_WAIT_TIME)
      self.ForceGarbageCollection(timeout_in_seconds)
    dump_id = self.tab.browser.DumpMemory(deterministic=deterministic_mode)
    if not dump_id:
      raise exceptions.StoryActionError('Unable to obtain memory dump')
    return dump_id

  def PrepareForLeakDetection(self):
    """Prepares for Leak Detection.

    Terminate workers, stopping spellcheckers, running GC etc.
    """
    self._tab.PrepareForLeakDetection()

  def Navigate(self, url, script_to_evaluate_on_commit=None,
               timeout_in_seconds=page_action.DEFAULT_TIMEOUT):
    """Navigates to |url|.

    If |script_to_evaluate_on_commit| is given, the script source string will be
    evaluated when the navigation is committed. This is after the context of
    the page exists, but before any script on the page itself has executed.
    """
    if six.moves.urllib.parse.urlparse(url).scheme == 'file':
      url = self._tab.browser.platform.http_server.UrlOf(url[7:])

    self._RunAction(NavigateAction(
        url=url,
        script_to_evaluate_on_commit=script_to_evaluate_on_commit,
        timeout_in_seconds=timeout_in_seconds))

  def NavigateBack(self):
    """ Navigate back to the previous page."""
    try:
      self.ExecuteJavaScript('window.history.back()')
    except exceptions.DevtoolsTargetClosedException:
      # Navigating back may immediately destroy the renderer, which devtools
      # communicates via a message that results in a
      # DevtoolsTargetClosedException. Continue on as this likely means the
      # navigation was successful.
      logging.warning('devtools closed navigating back, continuing')

  def WaitForNavigate(
      self, timeout_in_seconds_seconds=page_action.DEFAULT_TIMEOUT):
    start_time = time.time()
    self._tab.WaitForNavigate(timeout_in_seconds_seconds)

    time_left_in_seconds = (start_time + timeout_in_seconds_seconds
                            - time.time())
    time_left_in_seconds = max(0, time_left_in_seconds)
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter(
        time_left_in_seconds)

  def ReloadPage(self):
    """Reloads the page."""
    self._tab.ExecuteJavaScript('window.location.reload()')
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def ExecuteJavaScript(self, *args, **kwargs):
    """Executes a given JavaScript statement. Does not return the result.

    Example: runner.ExecuteJavaScript('var foo = {{ value }};', value='hi');

    Args:
      statement: The statement to execute (provided as a string).

    Optional keyword args:
      timeout: The number of seconds to wait for the statement to execute.
      Additional keyword arguments provide values to be interpolated within
          the statement. See telemetry.util.js_template for details.

    Raises:
      EvaluationException: The statement failed to execute.
    """
    if 'timeout' not in kwargs:
      kwargs['timeout'] = page_action.DEFAULT_TIMEOUT
    return self._tab.ExecuteJavaScript(*args, **kwargs)

  def EvaluateJavaScript(self, *args, **kwargs):
    """Returns the result of evaluating a given JavaScript expression.

    The evaluation results must be convertible to JSON. If the result
    is not needed, use ExecuteJavaScript instead.

    Example: runner.ExecuteJavaScript('document.location.href');

    Args:
      expression: The expression to execute (provided as a string).

    Optional keyword args:
      timeout: The number of seconds to wait for the expression to evaluate.
      Additional keyword arguments provide values to be interpolated within
          the expression. See telemetry.util.js_template for details.

    Raises:
      EvaluationException: The statement expression failed to execute
          or the evaluation result can not be JSON-ized.
    """
    if 'timeout' not in kwargs:
      kwargs['timeout'] = page_action.DEFAULT_TIMEOUT
    return self._tab.EvaluateJavaScript(*args, **kwargs)

  def WaitForJavaScriptCondition(self, *args, **kwargs):
    """Wait for a JavaScript condition to become true.

    Example: runner.WaitForJavaScriptCondition('window.foo == 10');

    Args:
      condition: The JavaScript condition (provided as string).

    Optional keyword args:
      timeout: The number in seconds to wait for the condition to become
          True (default to 60).
      Additional keyword arguments provide values to be interpolated within
          the expression. See telemetry.util.js_template for details.
    """
    if 'timeout' not in kwargs:
      kwargs['timeout'] = page_action.DEFAULT_TIMEOUT
    return self._tab.WaitForJavaScriptCondition(*args, **kwargs)

  def Wait(self, seconds):
    """Wait for the number of seconds specified.

    Args:
      seconds: The number of seconds to wait.
    """
    if not self._skip_waits:
      time.sleep(seconds)

  def WaitForElement(self, selector=None, text=None, element_function=None,
                     timeout_in_seconds=page_action.DEFAULT_TIMEOUT):
    """Wait for an element to appear in the document.

    The element may be selected via selector, text, or element_function.
    Only one of these arguments must be specified.

    Args:
      selector: A CSS selector describing the element.
      text: The element must contains this exact text.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          '(function() { return foo.element; })()'.
      timeout_in_seconds: The timeout in seconds.
    """
    self._RunAction(WaitForElementAction(
        selector=selector, text=text, element_function=element_function,
        timeout=timeout_in_seconds))

  def TapElement(self, selector=None, text=None, element_function=None,
                 timeout=page_action.DEFAULT_TIMEOUT):
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
        selector=selector, text=text, element_function=element_function,
        timeout=timeout))

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

  def DragPage(self, left_start_ratio, top_start_ratio, left_end_ratio,
               top_end_ratio, speed_in_pixels_per_second=800, use_touch=False,
               selector=None, text=None, element_function=None):
    """Perform a drag gesture on the page.

    You should specify a start and an end point in ratios of page width and
    height (see drag.js for full implementation).

    Args:
      left_start_ratio: The horizontal starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_start_ratio: The vertical starting coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      left_end_ratio: The horizontal ending coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      top_end_ratio: The vertical ending coordinate of the
          gesture, as a ratio of the visible bounding rectangle for
          document.body.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
      use_touch: Whether dragging should be done with touch input.
    """
    self._RunAction(DragAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        left_end_ratio=left_end_ratio, top_end_ratio=top_end_ratio,
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        use_touch=use_touch, selector=selector, text=text,
        element_function=element_function))

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
          The default scale factor is 3.0 / (current scale factor).
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(PinchAction(
        left_anchor_ratio=left_anchor_ratio, top_anchor_ratio=top_anchor_ratio,
        scale_factor=scale_factor,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def ScrollPage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                 direction='down', distance=None, distance_expr=None,
                 speed_in_pixels_per_second=800, use_touch=False,
                 synthetic_gesture_source=GESTURE_SOURCE_DEFAULT,
                 vsync_offset_ms=0.0,
                 input_event_pattern=INPUT_EVENT_PATTERN_DEFAULT):
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
          'up', 'down', 'upleft', 'upright', 'downleft', or 'downright'
      distance: The distance to scroll (in pixel).
      distance_expr: A JavaScript expression (as string) that can be
          evaluated to compute scroll distance. Example:
          'window.scrollTop' or '(function() { return crazyMath(); })()'.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
      use_touch: Whether scrolling should be done with touch input.
      synthetic_gesture_source: the source input device type for the
          synthetic gesture: 'DEFAULT', 'TOUCH' or 'MOUSE'.
    """
    assert synthetic_gesture_source in SUPPORTED_GESTURE_SOURCES
    self._RunAction(ScrollAction(
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, distance_expr=distance_expr,
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        use_touch=use_touch, synthetic_gesture_source=synthetic_gesture_source,
        vsync_offset_ms=vsync_offset_ms,
        input_event_pattern=input_event_pattern))

  def ScrollPageToElement(self, selector=None, element_function=None,
                          container_selector=None,
                          container_element_function=None,
                          speed_in_pixels_per_second=800):
    """Perform scroll gesture on container until an element is in view.

    Both the element and the container can be specified by a CSS selector
    xor a JavaScript function, provided as a string, which returns an element.
    The element is required so exactly one of selector and element_function
    must be provided. The container is optional so at most one of
    container_selector and container_element_function can be provided.
    The container defaults to document.scrollingElement or document.body if
    scrollingElement is not set.

    Args:
      selector: A CSS selector describing the element.
      element_function: A JavaScript function (as string) that is used
          to retrieve the element. For example:
          'function() { return foo.element; }'.
      container_selector: A CSS selector describing the container element.
      container_element_function: A JavaScript function (as a string) that is
          used to retrieve the container element.
      speed_in_pixels_per_second: Speed to scroll.
    """
    self._RunAction(ScrollToElementAction(
        selector=selector, element_function=element_function,
        container_selector=container_selector,
        container_element_function=container_element_function,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def RepeatableBrowserDrivenScroll(self, x_scroll_distance_ratio=0.0,
                                    y_scroll_distance_ratio=0.5,
                                    repeat_count=0,
                                    repeat_delay_ms=250,
                                    timeout=page_action.DEFAULT_TIMEOUT,
                                    prevent_fling=None,
                                    speed=None):
    """Perform a browser driven repeatable scroll gesture.

    The scroll gesture is driven from the browser, this is useful because the
    main thread often isn't resposive but the browser process usually is, so the
    delay between the scroll gestures should be consistent.

    Args:
      x_scroll_distance_ratio: The horizontal length of the scroll as a fraction
          of the screen width.
      y_scroll_distance_ratio: The vertical length of the scroll as a fraction
          of the screen height.
      repeat_count: The number of additional times to repeat the gesture.
      repeat_delay_ms: The delay in milliseconds between each scroll gesture.
      prevent_fling: Prevents a fling gesture.
      speed: Swipe speed in pixels per second.
    """
    self._RunAction(RepeatableScrollAction(
        x_scroll_distance_ratio=x_scroll_distance_ratio,
        y_scroll_distance_ratio=y_scroll_distance_ratio,
        repeat_count=repeat_count,
        repeat_delay_ms=repeat_delay_ms, timeout=timeout,
        prevent_fling=prevent_fling, speed=speed))

  def ScrollElement(self, selector=None, text=None, element_function=None,
                    left_start_ratio=0.5, top_start_ratio=0.5,
                    direction='down', distance=None, distance_expr=None,
                    speed_in_pixels_per_second=800, use_touch=False,
                    synthetic_gesture_source=GESTURE_SOURCE_DEFAULT,
                    vsync_offset_ms=0.0,
                    input_event_pattern=INPUT_EVENT_PATTERN_DEFAULT):
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
          'up', 'down', 'upleft', 'upright', 'downleft', or 'downright'
      distance: The distance to scroll (in pixel).
      distance_expr: A JavaScript expression (as string) that can be
          evaluated to compute scroll distance. Example:
          'window.scrollTop' or '(function() { return crazyMath(); })()'.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
      use_touch: Whether scrolling should be done with touch input.
      synthetic_gesture_source: the source input device type for the
          synthetic gesture: 'DEFAULT', 'TOUCH' or 'MOUSE'.
    """
    assert synthetic_gesture_source in SUPPORTED_GESTURE_SOURCES
    self._RunAction(ScrollAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance, distance_expr=distance_expr,
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        use_touch=use_touch, synthetic_gesture_source=synthetic_gesture_source,
        vsync_offset_ms=vsync_offset_ms,
        input_event_pattern=input_event_pattern))

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
          'up', 'down', 'upleft', 'upright', 'downleft', or 'downright'
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

  def ScrollBounceElement(
      self, selector=None, text=None, element_function=None,
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
          'up', 'down', 'upleft', 'upright', 'downleft', or 'downright'
      distance: The distance to scroll (in pixel).
      overscroll: The number of additional pixels to scroll back, in
          addition to the given distance.
      repeat_count: How often we want to repeat the full gesture.
      speed_in_pixels_per_second: The speed of the gesture (in pixels/s).
    """
    self._RunAction(ScrollBounceAction(
        selector=selector, text=text, element_function=element_function,
        left_start_ratio=left_start_ratio, top_start_ratio=top_start_ratio,
        direction=direction, distance=distance,
        overscroll=overscroll, repeat_count=repeat_count,
        speed_in_pixels_per_second=speed_in_pixels_per_second))

  def MouseClick(self, selector=None, timeout=page_action.DEFAULT_TIMEOUT):
    """Mouse click the given element.

    Args:
      selector: A CSS selector describing the element.
    """
    self._RunAction(MouseClickAction(selector=selector, timeout=timeout))

  def SwipePage(self, left_start_ratio=0.5, top_start_ratio=0.5,
                direction='left', distance=100, speed_in_pixels_per_second=800,
                timeout=page_action.DEFAULT_TIMEOUT):
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
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        timeout=timeout))

  def SwipeElement(self, selector=None, text=None, element_function=None,
                   left_start_ratio=0.5, top_start_ratio=0.5,
                   direction='left', distance=100,
                   speed_in_pixels_per_second=800,
                   timeout=page_action.DEFAULT_TIMEOUT):
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
        speed_in_pixels_per_second=speed_in_pixels_per_second,
        timeout=timeout))

  def PressKey(self, key, repeat_count=1, repeat_delay_ms=100,
               timeout=page_action.DEFAULT_TIMEOUT):
    """Perform a key press.

    Args:
      key: DOM value of the pressed key (e.g. 'PageDown', see
          https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/key).
      repeat_count: How many times the key should be pressed.
      repeat_delay_ms: Delay after each keypress (including the last one) in
          milliseconds.
    """
    for _ in range(repeat_count):
      self._RunAction(KeyPressAction(key, timeout=timeout))
      #2To3-division: this line is unchanged as result is expected floats.
      self.Wait(repeat_delay_ms / 1000.0)

  def EnterText(self, text, character_delay_ms=100,
                timeout=page_action.DEFAULT_TIMEOUT):
    """Enter text by performing key presses.

    Args:
      text: The text to enter.
      character_delay_ms: Delay after each keypress (including the last one) in
          milliseconds.
    """
    for c in text:
      self.PressKey(c, repeat_delay_ms=character_delay_ms, timeout=timeout)

  def LoadMedia(self, selector=None, event_timeout_in_seconds=0,
                event_to_await='canplaythrough'):
    """Invokes load() on media elements and awaits an event.

    Args:
      selector: A CSS selector describing the element. If none is
          specified, play the first media element on the page. If the
          selector matches more than 1 media element, all of them will
          be played.
      event_timeout_in_seconds: Maximum waiting time for the event to be fired.
          0 means do not wait.
      event_to_await: Which event to await. For example: 'canplaythrough' or
          'loadedmetadata'.

    Raises:
      TimeoutException: If the maximum waiting time is exceeded.
    """
    self._RunAction(LoadMediaAction(
        selector=selector, timeout_in_seconds=event_timeout_in_seconds,
        event_to_await=event_to_await))

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

  def ForceGarbageCollection(self, timeout_in_seconds=60):
    """Forces garbage collection on all relevant systems.

    This includes:
    - Java heap for browser and child subprocesses (on Android).
    - JavaScript on the current renderer.
    - System caches (on supported platforms).

    Args:
      timeout_in_seconds: maximum amount of time (seconds) to wait for each
          garbage collection to complete.
    """
    # 1) Perform V8 and Blink garbage collection. This may free java wrappers.
    self._tab.CollectGarbage(timeout_in_seconds)
    # 2) Perform Java garbage collection
    if self._tab.browser.supports_java_heap_garbage_collection:
      self._tab.browser.ForceJavaHeapGarbageCollection()
    # 3) Flush system caches. This affects GPU memory.
    if self._tab.browser.platform.SupportFlushEntireSystemCache():
      self._tab.browser.platform.FlushEntireSystemCache()
    # 4) Wait until the effect of Java GC and system cache flushing propagates.
    self.Wait(_GARBAGE_COLLECTION_PROPAGATION_TIME)
    # 5) Re-do V8 and Blink garbage collection to free garbage allocated
    # while waiting.
    self._tab.CollectGarbage(timeout_in_seconds)
    # 6) Finally, finish with V8 and Blink garbage collection because some
    # objects require V8 GC => Blink GC => V8 GC roundtrip.
    self._tab.CollectGarbage(timeout_in_seconds)

  def SimulateMemoryPressureNotification(self, pressure_level):
    """Simulate memory pressure notification.

    Args:
      pressure_level: 'moderate' or 'critical'.
    """
    self._tab.browser.SimulateMemoryPressureNotification(pressure_level)

  def EnterOverviewMode(self):
    if not self._tab.browser.supports_overview_mode:
      raise exceptions.StoryActionError('Overview mode is not supported')
    self._tab.browser.EnterOverviewMode()

  def ExitOverviewMode(self):
    if not self._tab.browser.supports_overview_mode:
      raise exceptions.StoryActionError('Overview mode is not supported')
    self._tab.browser.ExitOverviewMode()

  def PauseInteractive(self):
    """Pause the page execution and wait for terminal interaction.

    This is typically used for debugging. You can use this to pause
    the page execution and inspect the browser state before
    continuing.
    """
    input("Interacting... Press Enter to continue.")

  def RepaintContinuously(self, seconds):
    """Continuously repaints the visible content.

    It does this by requesting animation frames until the given number
    of seconds have elapsed AND at least three RAFs have been
    fired. Times out after max(60, self.seconds), if less than three
    RAFs were fired."""
    self._RunAction(RepaintContinuouslyAction(
        seconds=0 if self._skip_waits else seconds))

  def StartMobileDeviceEmulation(
      self, width=360, height=640, dsr=2, timeout=60):
    """Emulates a mobile device.

    This method is intended for benchmarks used to gather non-performance
    metrics only. Mobile emulation is not guaranteed to have the same
    performance characteristics as real devices.

    Example device parameters:
    https://gist.github.com/devinmancuso/0c94410cb14c83ddad6f

    Args:
      width: Screen width.
      height: Screen height.
      dsr: Screen device scale factor.
    """
    self._tab.StartMobileDeviceEmulation(width, height, dsr, timeout)

  def StopMobileDeviceEmulation(self, timeout=60):
    """Stops emulation of a mobile device."""
    self._tab.StopMobileDeviceEmulation(timeout)

  def EnableFetch(self,
                  patterns,
                  request_paused_callback=None,
                  auth_required_callback=None,
                  timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    self._tab.EnableFetch(patterns, request_paused_callback,
                          auth_required_callback, timeout)

  def DisableFetch(self, timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    self._tab.DisableFetch(timeout)

  def CreateContinueRequest(self,
                            request_id,
                            url=None,
                            method=None,
                            post_data=None,
                            headers=None):
    return self._tab.CreateContinueRequest(request_id, url, method, post_data,
                                           headers)

  def ContinueRequestSync(self, request, timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    return self._tab.ContinueRequestSync(request, timeout)

  def ContinueRequestAndIgnoreResponse(self, request):
    self._tab.ContinueRequestAndIgnoreResponse(request)

  def CreateContinueWithAuthRequest(self, request_id, auth_challenge_response):
    return self._tab.CreateContinueWithAuthRequest(request_id,
                                                   auth_challenge_response)

  def ContinueWithAuthRequestSync(self,
                                  request,
                                  timeout=_DEFAULT_WEBSOCKET_TIMEOUT):
    return self._tab.ContinueWithAuthRequestSync(request, timeout)

  def ContinueWithAuthRequestAndIgnoreResponse(self, request):
    self._tab.ContinueWithAuthRequestAndIgnoreResponse(request)

class Interaction():

  def __init__(self, action_runner, label, flags):
    assert action_runner
    assert label
    assert isinstance(flags, list)

    self._action_runner = action_runner
    self._label = label
    self._flags = flags
    self._started = False

  def __enter__(self):
    self.Begin()
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if exc_value is None:
      self.End()
    else:
      logging.warning(
          'Exception was raised in the with statement block, the end of '
          'interaction record is not marked.')

  def Begin(self):
    assert not self._started
    self._started = True
    self._action_runner.ExecuteJavaScript(
        'console.time({{ marker }});',
        marker=timeline_interaction_record.GetJavaScriptMarker(
            self._label, self._flags))

  def End(self):
    assert self._started
    self._started = False
    self._action_runner.ExecuteJavaScript(
        'console.timeEnd({{ marker }});',
        marker=timeline_interaction_record.GetJavaScriptMarker(
            self._label, self._flags))
