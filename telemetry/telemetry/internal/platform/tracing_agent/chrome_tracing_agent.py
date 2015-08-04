# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform.tracing_agent import (
    chrome_devtools_tracing_backend)
from telemetry.timeline import tracing_config

_DESKTOP_OS_NAMES = ['linux', 'mac', 'win']

# The trace config file path should be the same as specified in
# src/components/tracing/startup_tracing.cc
_CHROME_TRACE_CONFIG_DIR_ANDROID = '/data/local/.config/'
_CHROME_TRACE_CONFIG_DIR_DESKTOP = os.path.expanduser('~/.config/')
_CHROME_TRACE_CONFIG_FILE_NAME = 'chrome-trace-config.json'


class ChromeTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(ChromeTracingAgent, self).__init__(platform_backend)
    self._chrome_devtools_tracing_backend = (
      chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend(
        platform_backend))

  @classmethod
  def RegisterDevToolsClient(cls, devtools_client_backend, platform_backend):
    (chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend
        .RegisterDevToolsClient(devtools_client_backend, platform_backend))

  @classmethod
  def IsSupported(cls, platform_backend):
    return (chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend
      .IsSupported(platform_backend))

  def Start(self, trace_options, category_filter, timeout):
    return self._chrome_devtools_tracing_backend.Start(
        trace_options, category_filter, timeout)

  def Stop(self, trace_data_builder):
    self._chrome_devtools_tracing_backend.Stop(trace_data_builder)

  def _CreateTraceConfigFile(self, trace_options, category_filter):
    config = tracing_config.TracingConfig(trace_options, category_filter)
    if self._platform_backend.GetOSName() == 'android':
      self._CreateTraceConfigFileOnAndroid(config)
    elif self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES:
      self._CreateTraceConfigFileOnDesktop(config)
    else:
      raise NotImplementedError

  def _RemoveTraceConfigFile(self):
    if self._platform_backend.GetOSName() == 'android':
      self._RemoveTraceConfigFileOnAndroid()
    elif self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES:
      self._RemoveTraceConfigFileOnDesktop()
    else:
      raise NotImplementedError

  def _CreateTraceConfigFileOnAndroid(self, config):
    assert self._platform_backend.GetOSName() == 'android'
    self._platform_backend.device.RunShellCommand(
        ['mkdir', '-p', _CHROME_TRACE_CONFIG_DIR_ANDROID],
        check_return=True, as_root=True)
    self._platform_backend.device.WriteFile(
        os.path.join(_CHROME_TRACE_CONFIG_DIR_ANDROID,
                     _CHROME_TRACE_CONFIG_FILE_NAME),
        config.GetTraceConfigJsonString(), as_root=True)

  def _RemoveTraceConfigFileOnAndroid(self):
    assert self._platform_backend.GetOSName() == 'android'
    self._platform_backend.device.RunShellCommand(
        ['rm', '-f', os.path.join(_CHROME_TRACE_CONFIG_DIR_ANDROID,
                                  _CHROME_TRACE_CONFIG_FILE_NAME)],
        check_return=True, as_root=True)

  def _CreateTraceConfigFileOnDesktop(self, config):
    assert self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES
    if not os.path.exists(_CHROME_TRACE_CONFIG_DIR_DESKTOP):
      os.mkdir(_CHROME_TRACE_CONFIG_DIR_DESKTOP)
    with open(os.path.join(_CHROME_TRACE_CONFIG_DIR_DESKTOP,
                           _CHROME_TRACE_CONFIG_FILE_NAME), 'w') as f:
      f.write(config.GetTraceConfigJsonString())

  def _RemoveTraceConfigFileOnDesktop(self):
    assert self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES
    config_file_path = os.path.join(_CHROME_TRACE_CONFIG_DIR_DESKTOP,
                                    _CHROME_TRACE_CONFIG_FILE_NAME)
    if os.path.exists(config_file_path):
      os.remove(config_file_path)
