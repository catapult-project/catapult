# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys

from telemetry import decorators
from telemetry.core import bitmap
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core.backends.chrome import inspector_console
from telemetry.core.backends.chrome import inspector_memory
from telemetry.core.backends.chrome import inspector_network
from telemetry.core.backends.chrome import inspector_page
from telemetry.core.backends.chrome import inspector_runtime
from telemetry.core.backends.chrome import inspector_timeline
from telemetry.core.backends.chrome import inspector_websocket
from telemetry.core.backends.chrome import websocket
from telemetry.core.heap import model
from telemetry.timeline import model as timeline_model
from telemetry.timeline import recording_options


class InspectorException(Exception):
  pass


class InspectorBackend(inspector_websocket.InspectorWebsocket):
  def __init__(self, browser_backend, context, timeout=60):
    super(InspectorBackend, self).__init__(self._HandleNotification,
                                           self._HandleError)

    self._browser_backend = browser_backend
    self._context = context
    self._domain_handlers = {}

    logging.debug('InspectorBackend._Connect() to %s', self.debugger_url)
    try:
      self.Connect(self.debugger_url)
    except (websocket.WebSocketException, util.TimeoutException):
      err_msg = sys.exc_info()[1]
      if not self._browser_backend.IsBrowserRunning():
        raise exceptions.BrowserGoneException(self.browser, err_msg)
      elif not self._browser_backend.HasBrowserFinishedLaunching():
        raise exceptions.BrowserConnectionGoneException(self.browser, err_msg)
      else:
        raise exceptions.TabCrashException(self.browser, err_msg)

    self._console = inspector_console.InspectorConsole(self)
    self._memory = inspector_memory.InspectorMemory(self)
    self._page = inspector_page.InspectorPage(self, timeout=timeout)
    self._runtime = inspector_runtime.InspectorRuntime(self)
    self._timeline = inspector_timeline.InspectorTimeline(self)
    self._network = inspector_network.InspectorNetwork(self)
    self._timeline_model = None

  def __del__(self):
    self.Disconnect()

  def Disconnect(self):
    for _, handlers in self._domain_handlers.items():
      _, will_close_handler = handlers
      will_close_handler()
    self._domain_handlers = {}

    super(InspectorBackend, self).Disconnect()

  @property
  def browser(self):
    return self._browser_backend.browser

  @property
  def url(self):
    for c in self._browser_backend.ListInspectableContexts():
      if c['id'] == self._context['id']:
        return c['url']
    return None

  @property
  def id(self):
    return self.debugger_url

  @property
  def debugger_url(self):
    return self._context['webSocketDebuggerUrl']

  # Public methods implemented in JavaScript.

  @property
  @decorators.Cache
  def screenshot_supported(self):
    if (self.browser.platform.GetOSName() == 'linux' and (
        os.getenv('DISPLAY') not in [':0', ':0.0'])):
      # Displays other than 0 mean we are likely running in something like
      # xvfb where screenshotting doesn't work.
      return False
    return not self.EvaluateJavaScript("""
        window.chrome.gpuBenchmarking === undefined ||
        window.chrome.gpuBenchmarking.beginWindowSnapshotPNG === undefined
      """)

  def Screenshot(self, timeout):
    assert self.screenshot_supported, 'Browser does not support screenshotting'

    self.EvaluateJavaScript("""
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
      return self.EvaluateJavaScript(
          'window.__telemetry.snapshotComplete')

    util.WaitFor(IsSnapshotComplete, timeout)

    snap = self.EvaluateJavaScript("""
      (function() {
        var data = window.__telemetry.snapshotData;
        delete window.__telemetry.snapshotComplete;
        delete window.__telemetry.snapshotData;
        return data;
      })()
    """)
    if snap:
      return bitmap.Bitmap.FromBase64Png(snap['data'])
    return None

  # Console public methods.

  @property
  def message_output_stream(self):  # pylint: disable=E0202
    return self._console.message_output_stream

  @message_output_stream.setter
  def message_output_stream(self, stream):  # pylint: disable=E0202
    self._console.message_output_stream = stream

  # Memory public methods.

  def GetDOMStats(self, timeout):
    dom_counters = self._memory.GetDOMCounters(timeout)
    return {
      'document_count': dom_counters['documents'],
      'node_count': dom_counters['nodes'],
      'event_listener_count': dom_counters['jsEventListeners']
    }

  # Page public methods.

  def WaitForNavigate(self, timeout):
    self._page.WaitForNavigate(timeout)

  def Navigate(self, url, script_to_evaluate_on_commit, timeout):
    self._page.Navigate(url, script_to_evaluate_on_commit, timeout)

  def GetCookieByName(self, name, timeout):
    return self._page.GetCookieByName(name, timeout)

  # Runtime public methods.

  def ExecuteJavaScript(self, expr, context_id=None, timeout=60):
    self._runtime.Execute(expr, context_id, timeout)

  def EvaluateJavaScript(self, expr, context_id=None, timeout=60):
    return self._runtime.Evaluate(expr, context_id, timeout)

  def EnableAllContexts(self):
    return self._runtime.EnableAllContexts()

  # Timeline public methods.

  @property
  def timeline_model(self):
    return self._timeline_model

  def StartTimelineRecording(self, options=None):
    if not options:
      options = recording_options.TimelineRecordingOptions()
    if options.record_timeline:
      self._timeline.Start()
    if options.record_network:
      self._network.timeline_recorder.Start()

  def StopTimelineRecording(self):
    data = []
    timeline_data = self._timeline.Stop()
    if timeline_data:
      data.append(timeline_data)
    network_data = self._network.timeline_recorder.Stop()
    if network_data:
      data.append(network_data)
    if data:
      self._timeline_model = timeline_model.TimelineModel(
          timeline_data=data, shift_world_to_zero=False)
    else:
      self._timeline_model = None

  @property
  def is_timeline_recording_running(self):
    return self._timeline.is_timeline_recording_running

  # Network public methods.

  def ClearCache(self):
    self._network.ClearCache()

  # Methods used internally by other backends.

  def _IsInspectable(self):
    contexts = self._browser_backend.ListInspectableContexts()
    return self._context['id'] in [c['id'] for c in contexts]

  def _HandleNotification(self, res):
    if (res['method'] == 'Inspector.detached' and
        res.get('params', {}).get('reason', '') == 'replaced_with_devtools'):
      self._WaitForInspectorToGoAwayAndReconnect()
      return
    if res['method'] == 'Inspector.targetCrashed':
      raise exceptions.TabCrashException(self.browser)

    mname = res['method']
    dot_pos = mname.find('.')
    domain_name = mname[:dot_pos]
    if domain_name in self._domain_handlers:
      try:
        self._domain_handlers[domain_name][0](res)
      except Exception:
        import traceback
        traceback.print_exc()
    else:
      logging.debug('Unhandled inspector message: %s', res)

  def _HandleError(self, elapsed_time):
    if self._IsInspectable():
      raise util.TimeoutException(
          'Received a socket error in the browser connection and the tab '
          'still exists, assuming it timed out. '
          'Elapsed=%ds Error=%s' % (elapsed_time, sys.exc_info()[1]))
    raise exceptions.TabCrashException(self.browser,
        'Received a socket error in the browser connection and the tab no '
        'longer exists, assuming it crashed. Error=%s' % sys.exc_info()[1])

  def _WaitForInspectorToGoAwayAndReconnect(self):
    sys.stderr.write('The connection to Chrome was lost to the Inspector UI.\n')
    sys.stderr.write('Telemetry is waiting for the inspector to be closed...\n')
    super(InspectorBackend, self).Disconnect()
    self._socket.close()
    self._socket = None
    def IsBack():
      if not self._IsInspectable():
        return False
      try:
        self.Connect(self.debugger_url)
      except exceptions.TabCrashException, ex:
        if ex.message.message.find('Handshake Status 500') == 0:
          return False
        raise
      return True
    util.WaitFor(IsBack, 512)
    sys.stderr.write('\n')
    sys.stderr.write('Inspector\'s UI closed. Telemetry will now resume.\n')

  def RegisterDomain(self,
      domain_name, notification_handler, will_close_handler):
    """Registers a given domain for handling notification methods.

    For example, given inspector_backend:
       def OnConsoleNotification(msg):
          if msg['method'] == 'Console.messageAdded':
             print msg['params']['message']
          return
       def OnConsoleClose(self):
          pass
       inspector_backend.RegisterDomain('Console',
                                        OnConsoleNotification, OnConsoleClose)
       """
    assert domain_name not in self._domain_handlers
    self._domain_handlers[domain_name] = (notification_handler,
                                          will_close_handler)

  def UnregisterDomain(self, domain_name):
    """Unregisters a previously registered domain."""
    assert domain_name in self._domain_handlers
    self._domain_handlers.pop(domain_name)

  def CollectGarbage(self):
    self._page.CollectGarbage()

  def TakeJSHeapSnapshot(self, timeout=120):
    snapshot = []

    def OnNotification(res):
      if res['method'] == 'HeapProfiler.addHeapSnapshotChunk':
        snapshot.append(res['params']['chunk'])

    def OnClose():
      pass

    self.RegisterDomain('HeapProfiler', OnNotification, OnClose)

    self.SyncRequest({'method': 'Page.getResourceTree'}, timeout)
    self.SyncRequest({'method': 'Debugger.enable'}, timeout)
    self.SyncRequest({'method': 'HeapProfiler.takeHeapSnapshot'}, timeout)
    snapshot = ''.join(snapshot)

    self.UnregisterDomain('HeapProfiler')
    return model.Model(snapshot)
