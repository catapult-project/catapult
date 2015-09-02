# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import stat
import tempfile

from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform.tracing_agent import (
    chrome_devtools_tracing_backend)

_DESKTOP_OS_NAMES = ['linux', 'mac', 'win']

# The trace config file path should be the same as specified in
# src/components/tracing/startup_tracing.cc
_CHROME_TRACE_CONFIG_DIR_ANDROID = '/data/local/'
_CHROME_TRACE_CONFIG_FILE_NAME = 'chrome-trace-config.json'


class ChromeTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(ChromeTracingAgent, self).__init__(platform_backend)
    self._chrome_devtools_tracing_backend = (
      chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend(
        platform_backend))
    self._trace_config_file = None

  @property
  def trace_config_file(self):
    return self._trace_config_file

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

  def _CreateTraceConfigFile(self, config):
    assert not self._trace_config_file
    if self._platform_backend.GetOSName() == 'android':
      self._trace_config_file = os.path.join(_CHROME_TRACE_CONFIG_DIR_ANDROID,
                                             _CHROME_TRACE_CONFIG_FILE_NAME)
      self._platform_backend.device.WriteFile(self._trace_config_file,
          config.GetTraceConfigJsonString(), as_root=True)
    elif self._platform_backend.GetOSName() in _DESKTOP_OS_NAMES:
      self._trace_config_file = os.path.join(tempfile.mkdtemp(),
                                             _CHROME_TRACE_CONFIG_FILE_NAME)
      with open(self._trace_config_file, 'w') as f:
        f.write(config.GetTraceConfigJsonString())
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
