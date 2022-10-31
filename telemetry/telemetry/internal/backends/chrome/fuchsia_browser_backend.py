# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
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


WEB_ENGINE_SHELL = 'web-engine-shell'
CAST_STREAMING_SHELL = 'cast-streaming-shell'
FUCHSIA_CHROME = 'fuchsia-chrome'


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
    self._command_runner = fuchsia_platform_backend.command_runner
    self._browser_process = None
    self._devtools_port = None
    self._symbolizer_proc = None
    if os.environ.get('CHROMIUM_OUTPUT_DIR'):
      self._output_dir = os.environ.get('CHROMIUM_OUTPUT_DIR')
    else:
      self._output_dir = os.path.abspath(os.path.dirname(
          fuchsia_platform_backend.ssh_config))
    self._browser_log = ''
    self._browser_log_proc = None
    self._managed_repo = fuchsia_platform_backend.managed_repo

  @property
  def log_file_path(self):
    return None

  def _FindDevToolsPortAndTarget(self):
    return self._devtools_port, None

  def DumpMemory(self, timeout=None, detail_level=None):
    if detail_level is None:
      detail_level = 'light'
    return self.devtools_client.DumpMemory(timeout=timeout,
                                           detail_level=detail_level)

  def _ReadDevToolsPortFromPipe(self, search_regex, pipe):
    def TryReadingPort():
      if not pipe:
        return None
      line = pipe.readline()
      tokens = re.search(search_regex, line)
      self._browser_log += line
      return int(tokens.group(1)) if tokens else None
    return py_utils.WaitFor(TryReadingPort, timeout=60)

  def _ReadDevToolsPort(self):
    read_port_mapping = {
        WEB_ENGINE_SHELL: {
            'search_regex': r'Remote debugging port: (\d+)',
            'pipe': self._browser_log_proc.stdout,
        },
        CAST_STREAMING_SHELL: {
            'search_regex': r'Remote debugging port: (\d+)',
            'pipe': self._browser_log_proc.stderr,
        },
        FUCHSIA_CHROME: {
            'search_regex': ('DevTools listening on'
                             r' ws://127.0.0.1:(\d+)/devtools.*'),
            'pipe': self._browser_log_proc.stderr,
        }
    }
    if self.browser_type not in read_port_mapping:
      raise NotImplementedError(f'Browser {self.browser_type} is not supported')

    result = self._ReadDevToolsPortFromPipe(
        **read_port_mapping[self.browser_type])

    return result

  def _StartWebEngineShell(self, startup_args):
    browser_cmd = [
        'test',
        'run',
        'fuchsia-pkg://%s/web_engine_shell#meta/web_engine_shell.cm' %
        self._managed_repo,
    ]

    # Flags forwarded to the web_engine_shell component.
    browser_cmd.extend([
        '--',
        '--web-engine-package-name=web_engine_with_webui',
        '--remote-debugging-port=0',
        '--use-web-instance',
        '--enable-web-instance-tmp',
        '--with-webui',
        'about:blank'
    ])

    # Use flags used on WebEngine in production devices.
    browser_cmd.extend([
        '--',
        '--enable-low-end-device-mode',
        '--force-gpu-mem-available-mb=64',
        '--force-gpu-mem-discardable-limit-mb=32',
        '--force-max-texture-size=2048',
        '--gpu-rasterization-msaa-sample-count=0',
        '--min-height-for-gpu-raster-tile=128',
        '--webgl-msaa-sample-count=0',
        '--max-decoded-image-size-mb=10'
    ])
    if startup_args:
      browser_cmd.extend(startup_args)
    self._browser_process = self._command_runner.run_continuous_ffx_command(
        browser_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self._browser_log_proc = self._browser_process

  def _StartCastStreamingShell(self, startup_args):
    browser_cmd = [
        'run',
        'fuchsia-pkg://%s/cast_streaming_shell#meta/cast_streaming_shell.cmx' %
        self._managed_repo,
        '--remote-debugging-port=0',
    ]

    # Use flags used on WebEngine in production devices.
    browser_cmd.extend([
        '--',
        '--enable-low-end-device-mode',
        '--force-gpu-mem-available-mb=64',
        '--force-gpu-mem-discardable-limit-mb=32',
        '--force-max-texture-size=2048',
        '--gpu-rasterization-msaa-sample-count=0',
        '--min-height-for-gpu-raster-tile=128',
        '--webgl-msaa-sample-count=0',
        '--max-decoded-image-size-mb=10',
    ])
    if startup_args:
      browser_cmd.extend(startup_args)
    self._browser_process = self._command_runner.RunCommandPiped(
        browser_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self._browser_log_proc = self._browser_process

  def _StartChrome(self, startup_args):
    browser_cmd = [
        'session',
        'add',
        'fuchsia-pkg://%s/chrome#meta/chrome_v1.cmx' %
        self._managed_repo,
        '--',
        'about:blank',
        '--remote-debugging-port=0',
        '--enable-logging'
    ]
    if startup_args:
      browser_cmd.extend(startup_args)

    # Log the browser from this point on from system-logs.
    logging_cmd = [
        'log_listener',
        '--since_now'
    ]
    # Combine to STDOUT, as this is used for symbolization
    self._browser_log_proc = self._command_runner.RunCommandPiped(
        logging_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    # Need stderr to replicate stdout for symbolization.
    self._browser_log_proc.stderr = self._browser_log_proc.stdout

    logging.debug('Browser command: %s', ' '.join(browser_cmd))
    self._browser_process = self._command_runner.run_continuous_ffx_command(
        browser_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  def Start(self, startup_args):
    output_root = os.path.join(self._output_dir, 'gen', 'fuchsia_web')

    try:
      if self.browser_type == WEB_ENGINE_SHELL:
        self._StartWebEngineShell(startup_args)
        browser_id_files = [
            os.path.join(output_root, 'shell', 'web_engine_shell', 'ids.txt'),
            os.path.join(output_root, 'webengine', 'web_engine', 'ids.txt'),
        ]
      elif self.browser_type == CAST_STREAMING_SHELL:
        self._StartCastStreamingShell(startup_args)
        browser_id_files = [
            os.path.join(output_root, 'shell', 'cast_streaming_shell',
                'ids.txt'),
            os.path.join(output_root, 'webengine', 'web_engine', 'ids.txt'),
        ]
      else:
        self._StartChrome(startup_args)
        browser_id_files = [
            os.path.join(self._output_dir, 'gen', 'chrome', 'app', 'chrome',
                         'ids.txt'),
        ]

      # Symbolize stderr of browser process if possible
      self._symbolizer_proc = (
          fuchsia_interface.StartSymbolizerForProcessIfPossible(
              self._browser_log_proc.stderr, subprocess.PIPE, browser_id_files))
      if self._symbolizer_proc:
        self._browser_log_proc.stderr = self._symbolizer_proc.stdout

      self._dump_finder = minidump_finder.MinidumpFinder(
          self.browser.platform.GetOSName(),
          self.browser.platform.GetArchName())
      self._devtools_port = self._ReadDevToolsPort()
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
    # TODO(crbug.com/1297717): This does not work if the browser process is
    # kicked off via ffx session add, as that process is on the host, and
    # exits immediately.
    return self._browser_process.pid

  def Background(self):
    raise NotImplementedError

  def _CloseOnDeviceBrowsers(self):
    if (self.browser_type == WEB_ENGINE_SHELL or
        self.browser_type == CAST_STREAMING_SHELL):
      close_cmd = ['killall', 'web_instance.cmx']
    else:
      close_cmd = ['killall', 'chrome_v1.cmx']
    self._command_runner.RunCommand(
        close_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  def Close(self):
    super().Close()

    if self._browser_process:
      logging.info('Shutting down browser process on Fuchsia')
      self._browser_process.kill()
    if self._browser_log_proc:
      self._browser_log_proc.kill()
    if self._symbolizer_proc:
      self._symbolizer_proc.kill()
    self._CloseOnDeviceBrowsers()
    self._browser_process = None
    self._browser_log_proc = None

  def IsBrowserRunning(self):
    # TODO(crbug.com/1297717): this does not capture if the process is still
    # running if its kicked off via ffx session add.
    return bool(self._browser_process)

  def GetStandardOutput(self):
    if self._browser_log_proc:
      self._browser_log_proc.terminate()
      self._CloseOnDeviceBrowsers()

      # Make sure there is something to read.
      if select.select([self._browser_log_proc.stderr], [], [], 0.0)[0]:
        self._browser_log += self._browser_log_proc.stderr.read()
    return self._browser_log

  def SymbolizeMinidump(self, minidump_path):
    logging.warning('Symbolizing Minidump not supported on Fuchsia.')

  def _GetBrowserExecutablePath(self):
    return None
