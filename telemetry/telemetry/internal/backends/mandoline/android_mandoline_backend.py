# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import random
import re
import sys

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.internal.backends.mandoline import android
from telemetry.internal.backends.mandoline import config
from telemetry.internal.backends.mandoline import mandoline_browser_backend
from telemetry.internal.platform import android_platform_backend as \
  android_platform_backend_module

try:
  from pylib import constants
except ImportError:
  pass

class AndroidMandolineBackend(
    mandoline_browser_backend.MandolineBrowserBackend):
  """The backend for controlling a mandoline browser instance running on
  Android."""

  def __init__(self, android_platform_backend, browser_options, target_arch,
               browser_type, build_path, package, chrome_root):
    assert isinstance(android_platform_backend,
                      android_platform_backend_module.AndroidPlatformBackend)
    super(AndroidMandolineBackend, self).__init__(
        android_platform_backend,
        browser_options=browser_options)

    self._target_arch = target_arch
    self._browser_type = browser_type
    self._build_path = build_path
    self._package = package
    self._device_port = None
    self._chrome_root = chrome_root

    # TODO(wuhu): Move to network controller backend.
    self.platform_backend.InstallTestCa()

    # Kill old browser.
    self._KillBrowser()

  @property
  def device(self):
    return self.platform_backend.device

  def _KillBrowser(self):
    if self.device.IsUserBuild():
      self.platform_backend.StopApplication(self._package)
    else:
      self.platform_backend.KillApplication(self._package)

  def Start(self):
    self.device.RunShellCommand('logcat -c')

    self.platform_backend.DismissCrashDialogIfNeeded()

    self._port = util.GetUnreservedAvailableLocalPort()
    self._device_port = self._GetAvailableDevicePort()

    self.device.adb.Forward('tcp:%d' % self._port, 'tcp:%d' % self._device_port)
    logging.info('Forwarded host port %d to device port %d.' %
                     (self._port, self._device_port))

    args = self.GetBrowserStartupArgs()

    if self.browser_options.startup_url:
      args.append(self.browser_options.startup_url)

    logging.debug('Starting Mandoline %s', args)

    is_debug = 'debug' in self._browser_type
    mandoline_config = config.Config(build_dir=self._build_path,
                                     target_os=config.Config.OS_ANDROID,
                                     target_cpu=self._target_arch,
                                     is_debug=is_debug,
                                     apk_name='Mandoline.apk')
    shell = android.AndroidShell(mandoline_config, self._chrome_root)
    shell.InitShell(self.device)

    output = sys.stdout
    if not self.browser_options.show_stdout:
      output = open(os.devnull, 'w')
    logging_process = shell.ShowLogs(output)

    # Unlock device screen.
    self.device.SendKeyEvent(constants.keyevent.KEYCODE_MENU)
    shell.StartActivity(self.activity, args, output, logging_process.terminate)

    try:
      self._WaitForBrowserToComeUp()
      self._InitDevtoolsClientBackend(self._port)
    except exceptions.BrowserGoneException:
      logging.critical('Failed to connect to browser.')
      self.Close()
      raise
    except:
      self.Close()
      raise

  def GetBrowserStartupArgs(self):
    args = super(AndroidMandolineBackend, self).GetBrowserStartupArgs()
    # TODO(yzshen): Mandoline on Android doesn't support excessively long
    # command line yet. Remove fieldtrial-related flags as a temp fix because
    # they are long and not processed by Mandoline anyway.
    # http://crbug.com/514285
    args = [arg for arg in args if arg.find('--force-fieldtrials=') == -1 and
                                   arg.find('--force-fieldtrial-params=') == -1]
    args.append('--remote-debugging-port=%i' % self._device_port)
    return args

  @property
  def pid(self):
    pids = self.device.GetPids(self._package)
    if not pids or self._package not in pids:
      raise exceptions.BrowserGoneException(self.browser)
    return int(pids[self._package])

  @property
  def browser_directory(self):
    return None

  @property
  def profile_directory(self):
    raise NotImplementedError()

  @property
  def package(self):
    return self._package

  @property
  def activity(self):
    return 'MandolineActivity'

  def __del__(self):
    self.Close()

  def Close(self):
    super(AndroidMandolineBackend, self).Close()

    self.platform_backend.RemoveTestCa()

    self._KillBrowser()

    if self._port:
      self.platform_backend.StopForwardingHost(self._port)
      self._port = None
      self._device_port = None

  def IsBrowserRunning(self):
    return self.platform_backend.IsAppRunning(self._package)

  def GetStandardOutput(self):
    return self.platform_backend.GetStandardOutput()

  def GetStackTrace(self):
    return self.platform_backend.GetStackTrace(self._target_arch)

  @property
  def should_ignore_certificate_errors(self):
    return not self.platform_backend.is_test_ca_installed

  def _GetAvailableDevicePort(self):
    used_ports = []
    netstat_results = self.device.RunShellCommand(
        ['netstat', '-a'], check_return=True, large_output=True)
    pattern = re.compile(r"^(127\.0\.0\.1:|localhost:)(\d+)$")
    for single_connect in netstat_results:
      # Column 3 is the local address which we want to check with.
      connect_results = single_connect.split()
      if connect_results[0] != 'tcp':
        continue
      if len(connect_results) < 6:
        raise Exception('Unexpected format while parsing netstat line: ' +
                        single_connect)
      result = re.match(pattern, connect_results[3])
      if result:
        used_ports.append(int(result.group(2)))

    # The range of ephemeral ports on Android.
    dynamic_port_begin = 32768
    dynamic_port_end = 61000
    assert len(used_ports) < dynamic_port_end - dynamic_port_begin + 1

    available_port = random.randint(dynamic_port_begin, dynamic_port_end)
    while available_port in used_ports:
      available_port = random.randint(dynamic_port_begin, dynamic_port_end)

    return available_port
