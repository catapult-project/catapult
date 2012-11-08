# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from telemetry import util

class InspectorPage(object):
  def __init__(self, inspector_backend):
    self._inspector_backend = inspector_backend
    self._inspector_backend.RegisterDomain(
        'Page',
        self._OnNotification,
        self._OnClose)
    self._pending_navigate_url = None

  def _OnNotification(self, msg):
    logging.debug('Notification: %s', json.dumps(msg, indent=2))
    if msg['method'] == 'Page.frameNavigated' and self._pending_navigate_url:
      url = msg['params']['frame']['url']
      if not url == 'chrome://newtab/':
        # Marks the navigation as complete and unblocks the navigate call.
        self._pending_navigate_url = None

  def _OnClose(self):
    pass

  def Navigate(self, url, timeout=60):
    """Navigates to url"""
    # Turn on notifications. We need them to get the Page.frameNavigated event.
    request = {
      'method': 'Page.enable'
      }
    res = self._inspector_backend.SyncRequest(request, timeout)
    assert len(res['result'].keys()) == 0

    # Navigate the page. However, there seems to be a bug in chrome devtools
    # protocol where the request id for this event gets held on the browser side
    # pretty much indefinitely.
    #
    # So, instead of waiting for the event to actually complete, wait for the
    # Page.frameNavigated event.
    request = {
      'method': 'Page.navigate',
      'params': {
        'url': url,
        }
      }
    res = self._inspector_backend.SendAndIgnoreResponse(request)

    self._pending_navigate_url = url
    def IsNavigationDone(time_left):
      self._inspector_backend.DispatchNotifications(time_left)
      return self._pending_navigate_url == None

    util.WaitFor(IsNavigationDone, timeout, pass_time_left_to_func=True)

    # Turn off notifications.
    request = {
      'method': 'Page.disable'
      }
    res = self._inspector_backend.SyncRequest(request, timeout)
    assert len(res['result'].keys()) == 0

