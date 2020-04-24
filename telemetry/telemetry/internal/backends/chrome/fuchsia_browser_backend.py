# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import select
import subprocess

from telemetry.core import fuchsia_interface
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.backends.chrome import minidump_finder
from telemetry.internal.platform import fuchsia_platform_backend as fuchsia_platform_backend_module

import py_utils


class FuchsiaBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  def __init__(self, fuchsia_platform_backend, browser_options,
               browser_directory, profile_directory):
    assert isinstance(fuchsia_platform_backend,
                      fuchsia_platform_backend_module.FuchsiaPlatformBackend)
    super(FuchsiaBrowserBackend, self).__init__(
        fuchsia_platform_backend,
        browser_options=browser_options,
        browser_directory=browser_directory,
        profile_directory=profile_directory,
        supports_extensions=False,
        supports_tab_control=False)
    self._command_runner = fuchsia_platform_backend.command_runner
    self._browser_process = None
    self._devtools_port = None
    self._symbolizer_proc = None
    self._config_dir = fuchsia_platform_backend.config_dir
    self._browser_log = ''
    self._managed_repo = fuchsia_platform_backend.managed_repo

  @property
  def log_file_path(self):
    return None

  def _FindDevToolsPortAndTarget(self):
    return self._devtools_port, None

  def _ReadDevToolsPort(self, stderr):
    def TryReadingPort(f):
      if not f:
        return None
      line = f.readline()
      tokens = re.search(r'Remote debugging port: (\d+)', line)
      self._browser_log += line
      return int(tokens.group(1)) if tokens else None
    return py_utils.WaitFor(lambda: TryReadingPort(stderr), timeout=60)

  def _ConstructCmdLine(self, startup_args):
    del startup_args
    browser_cmd = [
        'run',
        'fuchsia-pkg://%s/web_engine_shell#meta/web_engine_shell.cmx' %
        self._managed_repo,
        '--remote-debugging-port=0',
        'about:blank'
    ]
    return browser_cmd

  def Start(self, startup_args):
    browser_cmd = self._ConstructCmdLine(startup_args)
    try:
      self._browser_process = self._command_runner.RunCommandPiped(
          browser_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

      browser_id_file = os.path.join(self._config_dir, 'gen', 'fuchsia',
                                     'engine', 'web_engine_shell', 'ids.txt')

      # Symbolize stderr of browser process if possible
      self._symbolizer_proc = (
          fuchsia_interface.StartSymbolizerForProcessIfPossible(
              self._browser_process.stderr, subprocess.PIPE, browser_id_file))
      if self._symbolizer_proc:
        self._browser_process.stderr = self._symbolizer_proc.stdout

      self._dump_finder = minidump_finder.MinidumpFinder(
          self.browser.platform.GetOSName(),
          self.browser.platform.GetArchName())
      self._devtools_port = self._ReadDevToolsPort(self._browser_process.stderr)
      self.BindDevToolsClient()
    except:
      logging.info('The browser failed to start. Output of the browser: \n%s' %
                   self.GetStandardOutput())
      self.Close()
      raise

  def GetPid(self):
    return self._browser_process.pid

  def Background(self):
    raise NotImplementedError

  def Close(self):
    super(FuchsiaBrowserBackend, self).Close()

    if self._browser_process:
      logging.info('Shutting down browser process on Fuchsia')
      self._browser_process.kill()
    if self._symbolizer_proc:
      self._symbolizer_proc.kill()
    self._browser_process = None

  def IsBrowserRunning(self):
    return bool(self._browser_process)

  def GetStandardOutput(self):
    if self._browser_process:
      # Make sure there is something to read.
      if select.select([self._browser_process.stderr], [], [], 0.0)[0]:
        self._browser_log += self._browser_process.stderr.read()
    return self._browser_log

  def SymbolizeMinidump(self, minidump_path):
    logging.warning('Symbolizing Minidump not supported on Fuchsia.')
    return None
