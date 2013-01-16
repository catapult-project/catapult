# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from telemetry import util

class InspectorPage(object):
  def __init__(self, tab_backend):
    self._tab_backend = tab_backend
    self._tab_backend.RegisterDomain(
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
    res = self._tab_backend.SyncRequest(request, timeout)
    assert len(res['result'].keys()) == 0

    def DisablePageNotifications():
      request = {
          'method': 'Page.disable'
          }
      res = self._tab_backend.SyncRequest(request, timeout)
      assert len(res['result'].keys()) == 0

    self._navigation_pending = True
    try:
      action_function()
    except:
      DisablePageNotifications()
      raise

    def IsNavigationDone(time_left):
      self._tab_backend.DispatchNotifications(time_left)
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
      self._tab_backend.SendAndIgnoreResponse(request)

    self.PerformActionAndWaitForNavigate(DoNavigate, timeout)

  def GetCookieByName(self, name, timeout=60):
    """Returns the value of the cookie by the given |name|."""
    request = {
        'method': 'Page.getCookies'
        }
    res = self._tab_backend.SyncRequest(request, timeout)
    cookies = res['result']['cookies']
    for cookie in cookies:
      if cookie['name'] == name:
        return cookie['value']
    return None
