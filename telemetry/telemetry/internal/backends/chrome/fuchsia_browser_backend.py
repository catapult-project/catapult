# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import logging

from telemetry.core import fuchsia_interface
from telemetry.internal.backends.chrome import (chrome_browser_backend,
                                                minidump_finder)
from telemetry.internal.platform import (fuchsia_platform_backend as
                                         fuchsia_platform_backend_module)


WEB_ENGINE_SHELL = 'web-engine-shell'
CAST_STREAMING_SHELL = 'cast-streaming-shell'
FUCHSIA_CHROME = 'fuchsia-chrome'

# The path is dynamically included since the fuchsia runner modules are not
# always available, and other platforms shouldn't depend on the fuchsia
# runners.
# pylint: disable=import-error,import-outside-toplevel


class FuchsiaBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  def __init__(self, fuchsia_platform_backend, browser_options,
               browser_directory, profile_directory):
    assert isinstance(fuchsia_platform_backend,
                      fuchsia_platform_backend_module.FuchsiaPlatformBackend)
    super().__init__(
        fuchsia_platform_backend,
        browser_options=browser_options,
        browser_directory=browser_directory,
        profile_directory=profile_directory,
        supports_extensions=False,
        supports_tab_control=True)
    fuchsia_interface.include_fuchsia_package()
    from browser_runner import BrowserRunner
    self._runner = BrowserRunner(
        self.browser_type, fuchsia_platform_backend.command_runner.target_id)

  @property
  def log_file_path(self):
    return None

  def _FindDevToolsPortAndTarget(self):
    return self._runner.devtools_port, None

  def DumpMemory(self, timeout=None, detail_level=None, deterministic=False):
    if detail_level is None:
      detail_level = 'light'
    return self.devtools_client.DumpMemory(timeout=timeout,
                                           detail_level=detail_level,
                                           deterministic=deterministic)

  def Start(self, startup_args):
    try:
      self._runner.start(startup_args)
      self._dump_finder = minidump_finder.MinidumpFinder(
          self.browser.platform.GetOSName(),
          self.browser.platform.GetArchName())
      self.BindDevToolsClient()

      # Start tracing if startup tracing attempted but did not actually start.
      # This occurs when no ChromeTraceConfig is present yet current_state is
      # non-None.
      tracing_backend = self._platform_backend.tracing_controller_backend
      current_state = tracing_backend.current_state
      if (not tracing_backend.GetChromeTraceConfig() and
          current_state is not None):
        tracing_backend.StopTracing()
        tracing_backend.StartTracing(current_state.config,
                                     current_state.timeout)

    except Exception as e:
      logging.exception(e)
      logging.error('The browser failed to start. Output of the browser: \n%s' %
                    self.GetStandardOutput())
      self.Close()
      raise

  def GetPid(self):
    return self._runner.browser_pid

  def Background(self):
    raise NotImplementedError

  def Close(self):
    super().Close()
    self._runner.close()

  def IsBrowserRunning(self):
    return self._runner.is_browser_running()

  def GetStandardOutput(self):
    with open(self._runner.log_file, encoding='utf-8') as log_file:
      return log_file.read()

  def SymbolizeMinidump(self, minidump_path):
    logging.warning('Symbolizing Minidump not supported on Fuchsia.')

  def _GetBrowserExecutablePath(self):
    return None
