# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import bitmap
from telemetry.core import web_contents

DEFAULT_TAB_TIMEOUT = 60


class BoundingBoxNotFoundException(Exception):
  pass


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
    self._previous_tab_contents_bounding_box = None

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

  def Highlight(self, color):
    """Synchronously highlights entire tab contents with the given RgbaColor.

    TODO(tonyg): It is possible that the z-index hack here might not work for
    all pages. If this happens, DevTools also provides a method for this.
    """
    self.ExecuteJavaScript("""
      (function() {
        var screen = document.createElement('div');
        screen.id = '__telemetry_screen_%d';
        screen.style.background = 'rgba(%d, %d, %d, %d)';
        screen.style.position = 'fixed';
        screen.style.top = '0';
        screen.style.left = '0';
        screen.style.width = '100%%';
        screen.style.height = '100%%';
        screen.style.zIndex = '2147483638';
        document.body.appendChild(screen);
        requestAnimationFrame(function() {
          screen.has_painted = true;
        });
      })();
    """ % (int(color), color.r, color.g, color.b, color.a))
    self.WaitForJavaScriptExpression(
      'document.getElementById("__telemetry_screen_%d").has_painted' %
      int(color), 5)

  def ClearHighlight(self, color):
    """Clears a highlight of the given bitmap.RgbaColor."""
    self.ExecuteJavaScript("""
      document.body.removeChild(
        document.getElementById('__telemetry_screen_%d'));
    """ % int(color))

  def StartVideoCapture(self, min_bitrate_mbps):
    """Starts capturing video of the tab's contents.

    This works by flashing the entire tab contents to a arbitrary color and then
    starting video recording. When the frames are processed, we can look for
    that flash as the content bounds.

    Args:
      min_bitrate_mbps: The minimum caputre bitrate in MegaBits Per Second.
          The platform is free to deliver a higher bitrate if it can do so
          without increasing overhead.
    """
    self.Highlight(bitmap.WEB_PAGE_TEST_ORANGE)
    self.browser.platform.StartVideoCapture(min_bitrate_mbps)
    self.ClearHighlight(bitmap.WEB_PAGE_TEST_ORANGE)

  def _FindHighlightBoundingBox(self, bmp, color):
    """Returns the bounding box of the content highlight of the given color.

    Raises:
      BoundingBoxNotFoundException if the hightlight could not be found.
    """
    content_box, pixel_count = bmp.GetBoundingBox(color, tolerance=8)

    if not content_box:
      raise BoundingBoxNotFoundException('Failed to find tab contents.')

    # We assume arbitrarily that tabs are all larger than 200x200. If this
    # fails it either means that assumption has changed or something is
    # awry with our bounding box calculation.
    if content_box[2] < 200 or content_box[3] < 200:
      raise BoundingBoxNotFoundException('Unexpectedly small tab contents.')

    # TODO(tonyg): Can this threshold be increased?
    if pixel_count < 0.9 * content_box[2] * content_box[3]:
      raise BoundingBoxNotFoundException(
          'Low count of pixels in tab contents matching expected color.')

    # Since Telemetry doesn't know how to resize the window, we assume
    # that we should always get the same content box for a tab. If this
    # fails, it means either that assumption has changed or something is
    # awry with our bounding box calculation. If this assumption changes,
    # this can be removed.
    #
    # TODO(tonyg): This assert doesn't seem to work.
    if (self._previous_tab_contents_bounding_box and
        self._previous_tab_contents_bounding_box != content_box):
      raise BoundingBoxNotFoundException(
          'Unexpected change in tab contents box.')
    self._previous_tab_contents_bounding_box = content_box

    return content_box

  def StopVideoCapture(self):
    """Stops recording video of the tab's contents.

    This looks for the initial color flash in the first frame to establish the
    tab content boundaries and then omits all frames displaying the flash.

    Yields:
      (time_ms, bitmap) tuples representing each video keyframe. Only the first
      frame in a run of sequential duplicate bitmaps is typically included.
        time_ms is milliseconds since navigationStart.
        bitmap is a telemetry.core.Bitmap.
    """
    frame_generator = self.browser.platform.StopVideoCapture()

    # Use initial flash to identify the content box, but skip over it.
    timestamp = 0
    content_box = None
    for timestamp, bmp in frame_generator:
      try:
        content_box = self._FindHighlightBoundingBox(
            bmp, bitmap.WEB_PAGE_TEST_ORANGE)
      except BoundingBoxNotFoundException:
        if not content_box:
          raise  # Content box is not in first frame.
        break

    start_time = timestamp
    for timestamp, bmp in frame_generator:
      yield timestamp - start_time, bmp.Crop(*content_box)

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
