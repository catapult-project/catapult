# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core import web_contents

DEFAULT_TAB_TIMEOUT = 60

class Tab(web_contents.WebContents):
  """Represents a tab in the browser

  The important parts of the Tab object are in the runtime and page objects.
  E.g.:
      # Navigates the tab to a given url.
      tab.Navigate('http://www.google.com/')

      # Evaluates 1+1 in the tab's JavaScript context.
      tab.Evaluate('1+1')
  """
  def __init__(self, inspector_backend):
    super(Tab, self).__init__(inspector_backend)

  def __del__(self):
    super(Tab, self).__del__()

  @property
  def browser(self):
    """The browser in which this tab resides."""
    return self._inspector_backend.browser

  @property
  def url(self):
    return self._inspector_backend.url

  @property
  def dom_stats(self):
    """A dictionary populated with measured DOM statistics.

    Currently this dictionary contains:
    {
      'document_count': integer,
      'node_count': integer,
      'event_listener_count': integer
    }
    """
    dom_counters = self._inspector_backend.GetDOMStats(
        timeout=DEFAULT_TAB_TIMEOUT)
    assert (len(dom_counters) == 3 and
            all([x in dom_counters for x in ['document_count', 'node_count',
                                             'event_listener_count']]))
    return dom_counters


  def Activate(self):
    """Brings this tab to the foreground asynchronously.

    Not all browsers or browser versions support this method.
    Be sure to check browser.supports_tab_control.

    Please note: this is asynchronous. There is a delay between this call
    and the page's documentVisibilityState becoming 'visible', and yet more
    delay until the actual tab is visible to the user. None of these delays
    are included in this call."""
    self._inspector_backend.Activate()

  @property
  def screenshot_supported(self):
    """True if the browser instance is capable of capturing screenshots."""
    return self._inspector_backend.screenshot_supported

  def Screenshot(self, timeout=DEFAULT_TAB_TIMEOUT):
    """Capture a screenshot of the tab's contents.

    Returns:
      A telemetry.core.Bitmap.
    """
    return self._inspector_backend.Screenshot(timeout)

  @property
  def video_capture_supported(self):
    """True if the browser instance is capable of capturing video."""
    return self.browser.platform.CanCaptureVideo()

  def StartVideoCapture(self, min_bitrate_mbps):
    """Starts capturing video of the tab's contents.

    Args:
      min_bitrate_mbps: The minimum caputre bitrate in MegaBits Per Second.
          The platform is free to deliver a higher bitrate if it can do so
          without increasing overhead.
    """
    self.browser.platform.StartVideoCapture(min_bitrate_mbps)

  def StopVideoCapture(self):
    """Stops recording video of the tab's contents.

    Yields:
      (time_ms, bitmap) tuples representing each video keyframe. Only the first
      frame in a run of sequential duplicate bitmaps is included.
        time_ms is milliseconds since navigationStart.
        bitmap is a telemetry.core.Bitmap.
    """
    # TODO(tonyg/szym): platform's video capture may include offscreen content
    # from a webcam, OS framing and browser framing. However, this API must
    # return only the tab contents. So we need to display a color flash in the
    # tab and then crop out all the other pixels. We also need to translate that
    # initial flash time into navigationStart timespace.

    for t in self.browser.platform.StopVideoCapture():
      return t

  def PerformActionAndWaitForNavigate(
      self, action_function, timeout=DEFAULT_TAB_TIMEOUT):
    """Executes action_function, and waits for the navigation to complete.

    action_function must be a Python function that results in a navigation.
    This function returns when the navigation is complete or when
    the timeout has been exceeded.
    """
    self._inspector_backend.PerformActionAndWaitForNavigate(
        action_function, timeout)

  def Navigate(self, url, script_to_evaluate_on_commit=None,
               timeout=DEFAULT_TAB_TIMEOUT):
    """Navigates to url.

    If |script_to_evaluate_on_commit| is given, the script source string will be
    evaluated when the navigation is committed. This is after the context of
    the page exists, but before any script on the page itself has executed.
    """
    self._inspector_backend.Navigate(url, script_to_evaluate_on_commit, timeout)

  def GetCookieByName(self, name, timeout=DEFAULT_TAB_TIMEOUT):
    """Returns the value of the cookie by the given |name|."""
    return self._inspector_backend.GetCookieByName(name, timeout)

  def CollectGarbage(self):
    self._inspector_backend.CollectGarbage()

  def ClearCache(self):
    """Clears the browser's HTTP disk cache and the tab's HTTP memory cache."""
    self._inspector_backend.ClearCache()
