# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import stat
import sys
import tempfile
import traceback

from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform.tracing_agent import (
    chrome_tracing_devtools_manager)
from telemetry.timeline import tracing_config

_DESKTOP_OS_NAMES = ['linux', 'mac', 'win']
_STARTUP_TRACING_OS_NAMES = _DESKTOP_OS_NAMES + ['android']

# The trace config file path should be the same as specified in
# src/components/tracing/startup_tracing.cc
_CHROME_TRACE_CONFIG_DIR_ANDROID = '/data/local/'
_CHROME_TRACE_CONFIG_FILE_NAME = 'chrome-trace-config.json'


class ChromeTracingStartedError(Exception):
  pass


class ChromeTracingStoppedError(Exception):
  pass


class ChromeTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(ChromeTracingAgent, self).__init__(platform_backend)
    self._trace_config = None
    self._trace_config_file = None

  @property
  def trace_config(self):
    # Trace config is also used to check if Chrome tracing is running or not.
    return self._trace_config

  @property
  def trace_config_file(self):
    return self._trace_config_file

  @classmethod
  def IsStartupTracingSupported(cls, platform_backend):
    if platform_backend.GetOSName() in _STARTUP_TRACING_OS_NAMES:
      return True
    else:
      return False

  @classmethod
  def IsSupported(cls, platform_backend):
    if cls.IsStartupTracingSupported(platform_backend):
      return True
    else:
      return chrome_tracing_devtools_manager.IsSupported(platform_backend)

  def _StartStartupTracing(self, config):
    if not self.IsStartupTracingSupported(self._platform_backend):
      return False
    self._CreateTraceConfigFile(config)
    return True

  def _StartDevToolsTracing(self, trace_options, category_filter, timeout):
    if not chrome_tracing_devtools_manager.IsSupported(self._platform_backend):
      return False
    devtools_clients = (chrome_tracing_devtools_manager
        .GetActiveDevToolsClients(self._platform_backend))
    if not devtools_clients:
      return False
    for client in devtools_clients:
      if client.is_tracing_running:
        raise ChromeTracingStartedError(
            'Tracing is already running on devtools at port %s on platform'
            'backend %s.' % (client.remote_port, self._platform_backend))
      client.StartChromeTracing(
          trace_options, category_filter.filter_string, timeout)
    return True

  def Start(self, trace_options, category_filter, timeout):
    if not trace_options.enable_chrome_trace:
      return False

    if self._trace_config:
      raise ChromeTracingStartedError(
          'Tracing is already running on platform backend %s.'
          % self._platform_backend)

    if (trace_options.enable_android_graphics_memtrack and
        self._platform_backend.GetOSName() == 'android'):
      self._platform_backend.SetGraphicsMemoryTrackingEnabled(True)

    # Chrome tracing Agent needs to start tracing for chrome browsers that are
    # not yet started, and for the ones that already are. For the former, we
    # first setup the trace_config_file, which allows browsers that starts after
    # this point to use it for enabling tracing upon browser startup. For the
    # latter, we invoke start tracing command through devtools for browsers that
    # are already started and tracked by chrome_tracing_devtools_manager.
    config = tracing_config.TracingConfig(trace_options, category_filter)
    started_startup_tracing = self._StartStartupTracing(config)
    started_devtools_tracing = self._StartDevToolsTracing(
        trace_options, category_filter, timeout)
    if started_startup_tracing or started_devtools_tracing:
      self._trace_config = config
      return True
    return False

  def Stop(self, trace_data_builder):
    if not self._trace_config:
      raise ChromeTracingStoppedError(
          'Tracing is not running on platform backend %s.'
          % self._platform_backend)

    if self.IsStartupTracingSupported(self._platform_backend):
      self._RemoveTraceConfigFile()

    # We get all DevTools clients including the stale ones, so that we get an
    # exception if there is a stale client. This is because we will potentially
    # lose data if there is a stale client.
    devtools_clients = (chrome_tracing_devtools_manager
        .GetDevToolsClients(self._platform_backend))
    raised_execption_messages = []
    for client in devtools_clients:
      try:
        client.StopChromeTracing(trace_data_builder)
      except Exception:
        raised_execption_messages.append(
          'Error when trying to stop Chrome tracing on devtools at port %s:\n%s'
          % (client.remote_port,
             ''.join(traceback.format_exception(*sys.exc_info()))))

    if (self._trace_config.tracing_options.enable_android_graphics_memtrack and
        self._platform_backend.GetOSName() == 'android'):
      self._platform_backend.SetGraphicsMemoryTrackingEnabled(False)

    self._trace_config = None
    if raised_execption_messages:
      raise ChromeTracingStoppedError(
          'Exceptions raised when trying to stop Chrome devtool tracing:\n' +
          '\n'.join(raised_execption_messages))

  def _CreateTraceConfigFileString(self, config):
    # See src/components/tracing/trace_config_file.h for the format
    trace_config_str = config.GetTraceConfigJsonString()
    return '{"trace_config":' + trace_config_str + '}'

  def _CreateTraceConfigFile(self, config):
    assert not self._trace_config_file
    if self._platform_backend.GetOSName() == 'android':
      self._trace_config_file = os.path.join(_CHROME_TRACE_CONFIG_DIR_ANDROID,
                                             _CHROME_TRACE_CONFIG_FILE_NAME)
      self._platform_backend.device.WriteFile(self._trace_config_file,
          self._CreateTraceConfigFileString(config), as_root=True)
    elif self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES:
      self._trace_config_file = os.path.join(tempfile.mkdtemp(),
                                             _CHROME_TRACE_CONFIG_FILE_NAME)
      with open(self._trace_config_file, 'w') as f:
        f.write(self._CreateTraceConfigFileString(config))
      os.chmod(self._trace_config_file,
               os.stat(self._trace_config_file).st_mode | stat.S_IROTH)
    else:
      raise NotImplementedError

  def _RemoveTraceConfigFile(self):
    if not self._trace_config_file:
      return
    if self._platform_backend.GetOSName() == 'android':
      self._platform_backend.device.RunShellCommand(
          ['rm', '-f', self._trace_config_file], check_return=True,
          as_root=True)
    elif self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES:
      if os.path.exists(self._trace_config_file):
        os.remove(self._trace_config_file)
      shutil.rmtree(os.path.dirname(self._trace_config_file))
    else:
      raise NotImplementedError
    self._trace_config_file = None
