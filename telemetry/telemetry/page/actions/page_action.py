# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry import decorators

class PageActionNotSupported(Exception):
  pass

class PageActionFailed(Exception):
  pass


class PageAction(object):
  """Represents an action that a user might try to perform to a page."""

  def WillRunAction(self, tab):
    """Override to do action-specific setup before
    Test.WillRunAction is called."""
    pass

  def RunAction(self, tab):
    raise NotImplementedError()

  def CleanUp(self, tab):
    pass

def EvaluateCallbackWithElement(
    tab, callback_js, selector=None, text=None, element_function=None,
    wait=False, timeout_in_seconds=60):
  """Evaluates the JavaScript callback with the given element.

  The element may be selected via selector, text, or element_function.
  Only one of these arguments must be specified.

  Returns:
    The callback's return value, if any. The return value must be
    convertible to JSON.

  Args:
    tab: A telemetry.core.Tab object.
    callback_js: The JavaScript callback to call (as string).
        The callback receive 2 parameters: the element, and information
        string about what method was used to retrieve the element.
        Example: '''
          function(element, info) {
            if (!element) {
              throw Error('Can not find element: ' + info);
            }
            element.click()
          }'''
    selector: A CSS selector describing the element.
    text: The element must contains this exact text.
    element_function: A JavaScript function (as string) that is used
        to retrieve the element. For example:
        '(function() { return foo.element; })()'.
    wait: Whether to wait for the return value to be true.
    timeout_in_seconds: The timeout for wait (if waiting).
  """
  count = 0
  info_msg = ''
  if element_function is not None:
    count = count + 1
    info_msg = 'using element_function "%s"' % re.escape(element_function)
  if selector is not None:
    count = count + 1
    info_msg = 'using selector "%s"' % _EscapeSelector(selector)
    element_function = 'document.querySelector(\'%s\')' % _EscapeSelector(
        selector)
  if text is not None:
    count = count + 1
    info_msg = 'using exact text match "%s"' % re.escape(text)
    element_function = '''
        (function() {
          function _findElement(element, text) {
            if (element.innerHTML == text) {
              return element;
            }

            var childNodes = element.childNodes;
            for (var i = 0, len = childNodes.length; i < len; ++i) {
              var found = _findElement(childNodes[i], text);
              if (found) {
                return found;
              }
            }
            return null;
          }
          return _findElement(document, '%s');
        })()''' % text

  if count != 1:
    raise PageActionFailed(
        'Must specify 1 way to retrieve element, but %s was specified.' % count)

  code = '''
      (function() {
        var element = %s;
        var callback = %s;
        return callback(element, '%s');
      })()''' % (element_function, callback_js, info_msg)

  if wait:
    tab.WaitForJavaScriptExpression(code, timeout_in_seconds)
    return True
  else:
    return tab.EvaluateJavaScript(code)

def _EscapeSelector(selector):
  return selector.replace('\'', '\\\'')

def GetGestureSourceTypeFromOptions(tab):
  gesture_source_type = tab.browser.synthetic_gesture_source_type
  return 'chrome.gpuBenchmarking.' + gesture_source_type.upper() + '_INPUT'

@decorators.Cache
def IsGestureSourceTypeSupported(tab, gesture_source_type):
  # TODO(dominikg): remove once support for
  #                 'chrome.gpuBenchmarking.gestureSourceTypeSupported' has
  #                 been rolled into reference build.
  if tab.EvaluateJavaScript("""
      typeof chrome.gpuBenchmarking.gestureSourceTypeSupported ===
          'undefined'"""):
    return (tab.browser.platform.GetOSName() != 'mac' or
            gesture_source_type.lower() != 'touch')

  return tab.EvaluateJavaScript("""
      chrome.gpuBenchmarking.gestureSourceTypeSupported(
          chrome.gpuBenchmarking.%s_INPUT)"""
      % (gesture_source_type.upper()))
