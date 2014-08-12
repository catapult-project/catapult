# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import sys
import time

from telemetry.core import util


class InspectorPage(object):
  def __init__(self, inspector_backend, timeout=60):
    self._inspector_backend = inspector_backend
    self._inspector_backend.RegisterDomain(
        'Page',
        self._OnNotification,
        self._OnClose)

    self._navigation_pending = False
    self._navigation_url = ''  # Support for legacy backends.
    self._navigation_frame_id = ''
    self._navigated_frame_ids = None  # Holds frame ids while navigating.
    self._script_to_evaluate_on_commit = None
    # Turn on notifications. We need them to get the Page.frameNavigated event.
    self._EnablePageNotifications(timeout=timeout)

  def _OnNotification(self, msg):
    logging.debug('Notification: %s', json.dumps(msg, indent=2))
    if msg['method'] == 'Page.frameNavigated':
      url = msg['params']['frame']['url']
      if not self._navigated_frame_ids == None:
        frame_id = msg['params']['frame']['id']
        if self._navigation_frame_id == frame_id:
          self._navigation_frame_id = ''
          self._navigated_frame_ids = None
          self._navigation_pending = False
        else:
          self._navigated_frame_ids.add(frame_id)
      elif self._navigation_url == url:
        # TODO(tonyg): Remove this when Chrome 38 goes stable.
        self._navigation_url = ''
        self._navigation_pending = False
      elif (not url == 'chrome://newtab/' and not url == 'about:blank'
        and not 'parentId' in msg['params']['frame']):
        # Marks the navigation as complete and unblocks the
        # WaitForNavigate call.
        self._navigation_pending = False

  def _OnClose(self):
    pass

  def _SetScriptToEvaluateOnCommit(self, source):
    existing_source = (self._script_to_evaluate_on_commit and
                       self._script_to_evaluate_on_commit['source'])
    if source == existing_source:
      return
    if existing_source:
      request = {
          'method': 'Page.removeScriptToEvaluateOnLoad',
          'params': {
              'identifier': self._script_to_evaluate_on_commit['id'],
              }
          }
      self._inspector_backend.SyncRequest(request)
      self._script_to_evaluate_on_commit = None
    if source:
      request = {
          'method': 'Page.addScriptToEvaluateOnLoad',
          'params': {
              'scriptSource': source,
              }
          }
      res = self._inspector_backend.SyncRequest(request)
      self._script_to_evaluate_on_commit = {
          'id': res['result']['identifier'],
          'source': source
          }

  def _EnablePageNotifications(self, timeout=60):
    request = {
        'method': 'Page.enable'
        }
    res = self._inspector_backend.SyncRequest(request, timeout)
    assert len(res['result'].keys()) == 0

  def WaitForNavigate(self, timeout=60):
    """Waits for the navigation to complete.

    The current page is expect to be in a navigation. This function returns
    when the navigation is complete or when the timeout has been exceeded.
    """
    start_time = time.time()
    remaining_time = timeout
    self._navigation_pending = True
    try:
      while self._navigation_pending and remaining_time > 0:
        remaining_time = max(timeout - (time.time() - start_time), 0.0)
        self._inspector_backend.DispatchNotifications(remaining_time)
    except util.TimeoutException:
      # Since we pass remaining_time to DispatchNotifications, we need to
      # list the full timeout time in this message.
      raise util.TimeoutException('Timed out while waiting %ds for navigation. '
                                  'Error=%s' % (timeout, sys.exc_info()[1]))

  def Navigate(self, url, script_to_evaluate_on_commit=None, timeout=60):
    """Navigates to |url|.

    If |script_to_evaluate_on_commit| is given, the script source string will be
    evaluated when the navigation is committed. This is after the context of
    the page exists, but before any script on the page itself has executed.
    """

    self._SetScriptToEvaluateOnCommit(script_to_evaluate_on_commit)
    request = {
        'method': 'Page.navigate',
        'params': {
            'url': url,
            }
        }
    self._navigated_frame_ids = set()
    res = self._inspector_backend.SyncRequest(request, timeout)
    if 'frameId' in res['result']:
      # Modern backends are returning frameId from Page.navigate.
      # Use it here to unblock upon precise navigation.
      frame_id = res['result']['frameId']
      if frame_id in self._navigated_frame_ids:
        self._navigated_frame_ids = None
        return
      self._navigation_frame_id = frame_id
    else:
      # TODO(tonyg): Remove this when Chrome 38 goes stable.
      self._navigated_frame_ids = None
      self._navigation_url = url
    self.WaitForNavigate(timeout)

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

  def CollectGarbage(self, timeout=60):
    request = {
        'method': 'HeapProfiler.CollectGarbage'
        }
    self._inspector_backend.SyncRequest(request, timeout)
