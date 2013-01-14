# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from telemetry import util
from telemetry import png_bitmap

DEFAULT_SCREENSHOT_TIMEOUT = 60

class InspectorPage(object):
  def __init__(self, inspector_backend, tab):
    self._tab = tab
    self._inspector_backend = inspector_backend
    self._inspector_backend.RegisterDomain(
        'Page',
        self._OnNotification,
        self._OnClose)
    self._navigation_pending = False

  def _OnNotification(self, msg):
    logging.debug('Notification: %s', json.dumps(msg, indent=2))
    if msg['method'] == 'Page.frameNavigated' and self._navigation_pending:
      url = msg['params']['frame']['url']
      if not url == 'chrome://newtab/' and not url == 'about:blank':
        # Marks the navigation as complete and unblocks the
        # PerformActionAndWaitForNavigate call.
        self._navigation_pending = False

  def _OnClose(self):
    pass

  def PerformActionAndWaitForNavigate(self, action_function, timeout=60):
    """Executes action_function, and waits for the navigation to complete.

    action_function is expect to result in a navigation. This function returns
    when the navigation is complete or when the timeout has been exceeded.
    """

    # Turn on notifications. We need them to get the Page.frameNavigated event.
    request = {
        'method': 'Page.enable'
        }
    res = self._inspector_backend.SyncRequest(request, timeout)
    assert len(res['result'].keys()) == 0

    def DisablePageNotifications():
      request = {
          'method': 'Page.disable'
          }
      res = self._inspector_backend.SyncRequest(request, timeout)
      assert len(res['result'].keys()) == 0

    self._navigation_pending = True
    try:
      action_function()
    except:
      DisablePageNotifications()
      raise

    def IsNavigationDone(time_left):
      self._inspector_backend.DispatchNotifications(time_left)
      return not self._navigation_pending
    util.WaitFor(IsNavigationDone, timeout, pass_time_left_to_func=True)

    DisablePageNotifications()

  def Navigate(self, url, timeout=60):
    """Navigates to url"""

    def DoNavigate():
      # Navigate the page. However, there seems to be a bug in chrome devtools
      # protocol where the request id for this event gets held on the browser
      # side pretty much indefinitely.
      #
      # So, instead of waiting for the event to actually complete, wait for the
      # Page.frameNavigated event.
      request = {
          'method': 'Page.navigate',
          'params': {
              'url': url,
              }
          }
      self._inspector_backend.SendAndIgnoreResponse(request)

    self.PerformActionAndWaitForNavigate(DoNavigate, timeout)

  @property
  def screenshot_supported(self):
    """True if the browser instance is capable of capturing screenshots"""
    if self._tab.runtime.Evaluate(
        'window.chrome.gpuBenchmarking === undefined'):
      return False

    if self._tab.runtime.Evaluate(
        'window.chrome.gpuBenchmarking.windowSnapshotPNG === undefined'):
      return False

    return True

  def Screenshot(self, timeout=DEFAULT_SCREENSHOT_TIMEOUT):
    """Capture a screenshot of the window for rendering validation"""

    if self._tab.runtime.Evaluate(
        'window.chrome.gpuBenchmarking === undefined'):
      raise Exception("Browser was not started with --enable-gpu-benchmarking")

    if self._tab.runtime.Evaluate(
        'window.chrome.gpuBenchmarking.beginWindowSnapshotPNG === undefined'):
      raise Exception("Browser does not support window snapshot API.")

    self._tab.runtime.Evaluate("""
        if(!window.__telemetry) {
          window.__telemetry = {}
        }
        window.__telemetry.snapshotComplete = false;
        window.__telemetry.snapshotData = null;
        window.chrome.gpuBenchmarking.beginWindowSnapshotPNG(
          function(snapshot) {
            window.__telemetry.snapshotData = snapshot;
            window.__telemetry.snapshotComplete = true;
          }
        );
    """)

    def IsSnapshotComplete():
      return self._tab.runtime.Evaluate('window.__telemetry.snapshotComplete')

    util.WaitFor(IsSnapshotComplete, timeout)

    snap = self._tab.runtime.Evaluate("""
      (function() {
        var data = window.__telemetry.snapshotData;
        delete window.__telemetry.snapshotComplete;
        delete window.__telemetry.snapshotData;
        return data;
      })()
    """)
    if snap:
      return png_bitmap.PngBitmap(snap['data'])
    return None

  def GetCookieByName(self, name, timeout=60):
    """Returns the value of the cookie by the given |name|."""
    request = {
        'method': 'Page.getCookies'
        }
    res = self._inspector_backend.SyncRequest(request, timeout)
    cookies = res['result']['cookies']
    for cookie in cookies:
      if cookie['name'] == name:
        return cookie['value']
    return None
