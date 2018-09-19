# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging


class InspectorLog(object):
  def __init__(self, inspector_websocket):
    """Enables the Log domain of DevTools protocol.

    This class subscribes to DevTools log entries and forwards error entries
    to python logging system as warnings.

    See https://chromedevtools.github.io/devtools-protocol/1-3/Log
    """

    self._inspector_websocket = inspector_websocket
    self._inspector_websocket.RegisterDomain('Log', self._OnMessage)
    self._Enable()

  def _OnMessage(self, message):
    if message['method'] == 'Log.entryAdded':
      entry = message['params']['entry']
      if entry['level'] == 'error':
        logging.warning('DevTools console [%s]: %s %s',
                        entry['source'], entry['text'], entry.get('url', ''))

  def _Enable(self, timeout=10):
    self._inspector_websocket.SyncRequest({'method': 'Log.enable'}, timeout)
