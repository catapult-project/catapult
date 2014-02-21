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
    self._tab_contents_bounding_box = None

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
        screen.style.background = 'rgba(%d, %d, %d, %d)';
        screen.style.position = 'fixed';
        screen.style.top = '0';
        screen.style.left = '0';
        screen.style.width = '100%%';
        screen.style.height = '100%%';
        screen.style.zIndex = '2147483638';
        document.body.appendChild(screen);
        requestAnimationFrame(function() {
          window.__telemetry_screen_%d = screen;
        });
      })();
    """ % (color.r, color.g, color.b, color.a, int(color)))
    self.WaitForJavaScriptExpression(
        '!!window.__telemetry_screen_%d' % int(color), 5)

  def ClearHighlight(self, color):
    """Clears a highlight of the given bitmap.RgbaColor."""
    self.ExecuteJavaScript("""
      (function() {
        document.body.removeChild(window.__telemetry_screen_%d);
        requestAnimationFrame(function() {
          window.__telemetry_screen_%d = null;
        });
      })();
    """ % (int(color), int(color)))
    self.WaitForJavaScriptExpression(
        '!window.__telemetry_screen_%d' % int(color), 5)

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

  def _FindHighlightBoundingBox(self, bmp, color, bounds_tolerance=8,
      color_tolerance=8):
    """Returns the bounding box of the content highlight of the given color.

    Raises:
      BoundingBoxNotFoundException if the hightlight could not be found.
    """
    content_box, pixel_count = bmp.GetBoundingBox(color,
        tolerance=color_tolerance)

    if not content_box:
      return None

    # We assume arbitrarily that tabs are all larger than 200x200. If this
    # fails it either means that assumption has changed or something is
    # awry with our bounding box calculation.
    if content_box[2] < 200 or content_box[3] < 200:
      raise BoundingBoxNotFoundException('Unexpectedly small tab contents.')

    # TODO(tonyg): Can this threshold be increased?
    if pixel_count < 0.9 * content_box[2] * content_box[3]:
      raise BoundingBoxNotFoundException(
          'Low count of pixels in tab contents matching expected color.')

    # Since we allow some fuzziness in bounding box finding, we want to make
    # sure that the bounds are always stable across a run. So we cache the
    # first box, whatever it may be.
    #
    # This relies on the assumption that since Telemetry doesn't know how to
    # resize the window, we should always get the same content box for a tab.
    # If this assumption changes, this caching needs to be reworked.
    if not self._tab_contents_bounding_box:
      self._tab_contents_bounding_box = content_box

    # Verify that there is only minor variation in the bounding box. If it's
    # just a few pixels, we can assume it's due to compression artifacts.
    for x, y in zip(self._tab_contents_bounding_box, content_box):
      if abs(x - y) > bounds_tolerance:
        # If this fails, it means either that either the above assumption has
        # changed or something is awry with our bounding box calculation.
        raise BoundingBoxNotFoundException(
            'Unexpected change in tab contents box.')

    return self._tab_contents_bounding_box

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

    # Flip through frames until we find the initial tab contents flash.
    content_box = None
    for _, bmp in frame_generator:
      content_box = self._FindHighlightBoundingBox(
          bmp, bitmap.WEB_PAGE_TEST_ORANGE)
      if content_box:
        break

    if not content_box:
      raise BoundingBoxNotFoundException(
          'Failed to identify tab contents in video capture.')

    # Flip through frames until the flash goes away and emit that as frame 0.
    timestamp = 0
    for timestamp, bmp in frame_generator:
      if not self._FindHighlightBoundingBox(bmp, bitmap.WEB_PAGE_TEST_ORANGE):
        yield 0, bmp.Crop(*content_box)
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

  def ClearCache(self, force):
    """Clears the browser's networking related disk, memory and other caches.

    Args:
      force: Iff true, navigates to about:blank which destroys the previous
          renderer, ensuring that even "live" resources in the memory cache are
          cleared.
    """
    self.ExecuteJavaScript("""
        if (window.chrome && chrome.benchmarking &&
            chrome.benchmarking.clearCache) {
          chrome.benchmarking.clearCache();
          chrome.benchmarking.clearPredictorCache();
          chrome.benchmarking.clearHostResolverCache();
        }
    """)
    if force:
      self.Navigate('about:blank')
