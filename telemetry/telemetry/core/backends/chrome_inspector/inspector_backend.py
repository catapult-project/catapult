# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import logging
import os
import socket
import sys

from telemetry.core.backends.chrome_inspector import devtools_http
from telemetry.core.backends.chrome_inspector import inspector_console
from telemetry.core.backends.chrome_inspector import inspector_memory
from telemetry.core.backends.chrome_inspector import inspector_network
from telemetry.core.backends.chrome_inspector import inspector_page
from telemetry.core.backends.chrome_inspector import inspector_runtime
from telemetry.core.backends.chrome_inspector import inspector_websocket
from telemetry.core.backends.chrome_inspector import websocket
from telemetry.core import exceptions
from telemetry.core import util
from telemetry import decorators
from telemetry.image_processing import image_util
from telemetry.timeline import model as timeline_model_module
from telemetry.timeline import trace_data as trace_data_module


def _HandleInspectorWebSocketExceptions(func):
  """Decorator for converting inspector_websocket exceptions.

  When an inspector_websocket exception is thrown in the original function,
  this decorator converts it into a telemetry exception and adds debugging
  information.
  """
  @functools.wraps(func)
  def inner(inspector_backend, *args, **kwargs):
    try:
      return func(inspector_backend, *args, **kwargs)
    except (socket.error, websocket.WebSocketException,
            inspector_websocket.WebSocketDisconnected) as e:
      inspector_backend._ConvertExceptionFromInspectorWebsocket(e)

  return inner


class InspectorBackend(object):
  """Class for communicating with a devtools client.

  The owner of an instance of this class is responsible for calling
  Disconnect() before disposing of the instance.
  """
  def __init__(self, app, devtools_client, context, timeout=60):
    self._websocket = inspector_websocket.InspectorWebsocket()
    self._websocket.RegisterDomain(
        'Inspector', self._HandleInspectorDomainNotification)

    self._app = app
    self._devtools_client = devtools_client
    # Be careful when using the context object, since the data may be
    # outdated since this is never updated once InspectorBackend is
    # created. Consider an updating strategy for this. (For an example
    # of the subtlety, see the logic for self.url property.)
    self._context = context

    logging.debug('InspectorBackend._Connect() to %s', self.debugger_url)
    try:
      self._websocket.Connect(self.debugger_url)
    except (websocket.WebSocketException, exceptions.TimeoutException) as e:
      self._ConvertExceptionFromInspectorWebsocket(e)

    self._console = inspector_console.InspectorConsole(self._websocket)
    self._memory = inspector_memory.InspectorMemory(self._websocket)
    self._page = inspector_page.InspectorPage(
        self._websocket, timeout=timeout)
    self._runtime = inspector_runtime.InspectorRuntime(self._websocket)
    self._network = inspector_network.InspectorNetwork(self._websocket)
    self._timeline_model = None

  def Disconnect(self):
    """Disconnects the inspector websocket.

    This method intentionally leaves the self._websocket object around, so that
    future calls it to it will fail with a relevant error.
    """
    if self._websocket:
      self._websocket.Disconnect()

  def __del__(self):
    self.Disconnect()

  @property
  def app(self):
    return self._app

  @property
  def url(self):
    """Returns the URL of the tab, as reported by devtools.

    Raises:
      devtools_http.DevToolsClientConnectionError
    """
    return self._devtools_client.GetUrl(self.id)

  @property
  def id(self):
    return self._context['id']

  @property
  def debugger_url(self):
    return self._context['webSocketDebuggerUrl']

  def IsInspectable(self):
    """Whether the tab is inspectable, as reported by devtools."""
    try:
      return self._devtools_client.IsInspectable(self.id)
    except devtools_http.DevToolsClientConnectionError:
      return False

  # Public methods implemented in JavaScript.

  @property
  @decorators.Cache
  def screenshot_supported(self):
    if (self.app.platform.GetOSName() == 'linux' and (
        os.getenv('DISPLAY') not in [':0', ':0.0'])):
      # Displays other than 0 mean we are likely running in something like
      # xvfb where screenshotting doesn't work.
      return False
    return True

  @_HandleInspectorWebSocketExceptions
  def Screenshot(self, timeout):
    assert self.screenshot_supported, 'Browser does not support screenshotting'
    return self._page.CaptureScreenshot(timeout)

  # Console public methods.

  @property
  def message_output_stream(self):  # pylint: disable=E0202
    return self._console.message_output_stream

  @message_output_stream.setter
  def message_output_stream(self, stream):  # pylint: disable=E0202
    self._console.message_output_stream = stream

  # Memory public methods.

  @_HandleInspectorWebSocketExceptions
  def GetDOMStats(self, timeout):
    """Gets memory stats from the DOM.

    Raises:
      inspector_memory.InspectorMemoryException
      exceptions.TimeoutException
      exceptions.DevtoolsTargetCrashException
    """
    dom_counters = self._memory.GetDOMCounters(timeout)
    return {
      'document_count': dom_counters['documents'],
      'node_count': dom_counters['nodes'],
      'event_listener_count': dom_counters['jsEventListeners']
    }

  # Page public methods.

  @_HandleInspectorWebSocketExceptions
  def WaitForNavigate(self, timeout):
    self._page.WaitForNavigate(timeout)

  @_HandleInspectorWebSocketExceptions
  def Navigate(self, url, script_to_evaluate_on_commit, timeout):
    self._page.Navigate(url, script_to_evaluate_on_commit, timeout)

  @_HandleInspectorWebSocketExceptions
  def GetCookieByName(self, name, timeout):
    return self._page.GetCookieByName(name, timeout)

  # Runtime public methods.

  @_HandleInspectorWebSocketExceptions
  def ExecuteJavaScript(self, expr, context_id=None, timeout=60):
    """Executes a javascript expression without returning the result.

    Raises:
      exceptions.EvaluateException
      exceptions.WebSocketDisconnected
      exceptions.TimeoutException
      exceptions.DevtoolsTargetCrashException
    """
    self._runtime.Execute(expr, context_id, timeout)

  @_HandleInspectorWebSocketExceptions
  def EvaluateJavaScript(self, expr, context_id=None, timeout=60):
    """Evaluates a javascript expression and returns the result.

    Raises:
      exceptions.EvaluateException
      exceptions.WebSocketDisconnected
      exceptions.TimeoutException
      exceptions.DevtoolsTargetCrashException
    """
    return self._runtime.Evaluate(expr, context_id, timeout)

  @_HandleInspectorWebSocketExceptions
  def EnableAllContexts(self):
    """Allows access to iframes.

    Raises:
      exceptions.WebSocketDisconnected
      exceptions.TimeoutException
      exceptions.DevtoolsTargetCrashException
    """
    return self._runtime.EnableAllContexts()

  # Timeline public methods.

  @property
  def timeline_model(self):
    return self._timeline_model

  @_HandleInspectorWebSocketExceptions
  def StartTimelineRecording(self):
    self._network.timeline_recorder.Start()

  @_HandleInspectorWebSocketExceptions
  def StopTimelineRecording(self):
    builder = trace_data_module.TraceDataBuilder()

    data = self._network.timeline_recorder.Stop()
    if data:
      builder.AddEventsTo(trace_data_module.INSPECTOR_TRACE_PART, data)
    self._timeline_model = timeline_model_module.TimelineModel(
        builder.AsData(), shift_world_to_zero=False)

  # Network public methods.

  @_HandleInspectorWebSocketExceptions
  def ClearCache(self):
    self._network.ClearCache()

  # Methods used internally by other backends.

  def _HandleInspectorDomainNotification(self, res):
    if (res['method'] == 'Inspector.detached' and
        res.get('params', {}).get('reason', '') == 'replaced_with_devtools'):
      self._WaitForInspectorToGoAway()
      return
    if res['method'] == 'Inspector.targetCrashed':
      exception = exceptions.DevtoolsTargetCrashException(self.app)
      self._AddDebuggingInformation(exception)
      raise exception

  def _WaitForInspectorToGoAway(self):
    self._websocket.Disconnect()
    raw_input('The connection to Chrome was lost to the inspector ui.\n'
              'Please close the inspector and press enter to resume '
              'Telemetry run...')
    raise exceptions.DevtoolsTargetCrashException(
        self.app, 'Devtool connection with the browser was interrupted due to '
        'the opening of an inspector.')

  def _ConvertExceptionFromInspectorWebsocket(self, error):
    """Converts an Exception from inspector_websocket.

    This method always raises a Telemetry exception. It appends debugging
    information. The exact exception raised depends on |error|.

    Args:
      error: An instance of socket.error or websocket.WebSocketException.
    Raises:
      exceptions.TimeoutException: A timeout occured.
      exceptions.DevtoolsTargetCrashException: On any other error, the most
        likely explanation is that the devtool's target crashed.
    """
    if isinstance(error, websocket.WebSocketTimeoutException):
      new_error = exceptions.TimeoutException()
    else:
      new_error = exceptions.DevtoolsTargetCrashException(self.app)

    original_error_msg = 'Original exception:\n' + str(error)
    new_error.AddDebuggingMessage(original_error_msg)
    self._AddDebuggingInformation(new_error)

    raise new_error, None, sys.exc_info()[2]

  def _AddDebuggingInformation(self, error):
    """Adds debugging information to error.

    Args:
      error: An instance of exceptions.Error.
    """
    if self.IsInspectable():
      msg = (
          'Received a socket error in the browser connection and the tab '
          'still exists. The operation probably timed out.'
      )
    else:
      msg = (
          'Received a socket error in the browser connection and the tab no '
          'longer exists. The tab probably crashed.'
      )
    error.AddDebuggingMessage(msg)
    error.AddDebuggingMessage('Debugger url: %s' % self.debugger_url)

  @_HandleInspectorWebSocketExceptions
  def CollectGarbage(self):
    self._page.CollectGarbage()
