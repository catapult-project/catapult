# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.actions import page_action
from telemetry.internal.actions.scroll import ScrollAction


class ScrollToElementAction(page_action.PageAction):


  def __init__(self, selector=None, element_function=None,
               speed_in_pixels_per_second=800):
    """
    Args:
      selector: Css selector to find element with.
      element_function: js string that evaluates to an element.
      speed_in_pixels_per_second: Speed in pixels per second to scroll.
    """
    super(ScrollToElementAction, self).__init__()
    self._selector = selector
    self._element_function = element_function
    self._speed = speed_in_pixels_per_second
    self._distance = None
    self._direction = None
    self._scroller = None
    assert (self._selector or self._element_function), (
        'Must have either selector or element function')

  def WillRunAction(self, tab):
    if self._selector:
      # TODO(catapult:#3028): Fix interpolation of JavaScript values.
      element = 'document.querySelector("%s")' % self._selector
    else:
      element = self._element_function

    # TODO(catapult:#3028): Fix interpolation of JavaScript values.
    get_distance_js = '''
      (function(elem){
        var rect = elem.getBoundingClientRect();
        if (rect.bottom < 0) {
          // The bottom of the element is above the viewport.
          // Scroll up until the top of the element is on screen.
          return rect.top - (window.innerHeight / 2);
        }
        if (rect.top - window.innerHeight >= 0) {
          // rect.top provides the pixel offset of the element from the
          // top of the page. Because that exceeds the viewport's height,
          // we know that the element is below the viewport.
          return rect.top - (window.innerHeight / 2);
        }
        return 0;
      })(%s);
    ''' % element

    self._distance = tab.EvaluateJavaScript(get_distance_js)
    self._direction = 'down' if self._distance > 0 else 'up'
    self._distance = abs(self._distance)
    self._scroller = ScrollAction(direction=self._direction,
                                  distance=self._distance,
                                  speed_in_pixels_per_second=self._speed)

  def RunAction(self, tab):
    if self._distance == 0:  # Element is already in view.
      return
    self._scroller.WillRunAction(tab)
    self._scroller.RunAction(tab)
