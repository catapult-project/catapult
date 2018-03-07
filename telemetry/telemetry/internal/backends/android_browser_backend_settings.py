# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util

import py_utils


class AndroidBrowserBackendSettings(object):

  def __init__(self, package, activity, command_line_name, apk_name,
               devtools_port=NotImplemented, supports_tab_control=True):
    self._package = package
    self._activity = activity
    self._command_line_name = command_line_name
    self._devtools_port = devtools_port
    self._supports_tab_control = supports_tab_control
    self._apk_name = apk_name

  @property
  def package(self):
    return self._package

  @property
  def activity(self):
    return self._activity

  @property
  def command_line_name(self):
    return self._command_line_name

  @property
  def supports_tab_control(self):
    return self._supports_tab_control

  @property
  def profile_ignore_list(self):
    # Don't delete lib, since it is created by the installer.
    return ('lib', )

  def GetDevtoolsRemotePort(self, device):
    del device
    # By default return the devtools_port defined in the constructor.
    return self._devtools_port

  def FindLocalApk(self, device, chrome_root):
    # Subclasses may override this method to pick the correct apk based on
    # specific device features.
    del device  # Unused.
    if self._apk_name is None:
      return None
    else:
      return _FindLocalApk(chrome_root, self._apk_name)


class ChromeBaseBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, package, apk_name=None):
    super(ChromeBaseBackendSettings, self).__init__(
        package=package,
        activity='com.google.android.apps.chrome.Main',
        command_line_name='chrome-command-line',
        devtools_port='localabstract:chrome_devtools_remote',
        apk_name=apk_name)


class ChromePublicBackendSettings(ChromeBaseBackendSettings):
  def __init__(self, package):
    super(ChromePublicBackendSettings, self).__init__(
        package=package,
        apk_name='ChromePublic.apk')


class ChromeBackendSettings(ChromeBaseBackendSettings):
  def __init__(self, package):
    super(ChromeBackendSettings, self).__init__(
        package=package,
        # TODO(crbug.com/813047): Should override FindLocalApk instead.
        apk_name='Chrome.apk')


class ContentShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, package):
    super(ContentShellBackendSettings, self).__init__(
        package=package,
        activity='org.chromium.content_shell_apk.ContentShellActivity',
        command_line_name='content-shell-command-line',
        devtools_port='localabstract:content_shell_devtools_remote',
        supports_tab_control=False,
        apk_name='ContentShell.apk')


class WebviewBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self,
               package,
               activity='org.chromium.webview_shell.TelemetryActivity',
               command_line_name='webview-command-line',
               apk_name='SystemWebView.apk'):
    super(WebviewBackendSettings, self).__init__(
        package=package,
        activity=activity,
        command_line_name=command_line_name,
        devtools_port='localabstract:webview_devtools_remote_{pid}',
        supports_tab_control=False,
        # TODO(crbug.com/813047): Should override FindLocalApk instead.
        apk_name=apk_name)

  def GetDevtoolsRemotePort(self, device):
    # The DevTools socket name for WebView depends on the activity PID's.
    def get_activity_pid():
      return device.GetApplicationPids(self.package, at_most_one=True)

    pid = py_utils.WaitFor(get_activity_pid, timeout=30)
    return self._devtools_port.format(pid=pid)


class WebviewShellBackendSettings(WebviewBackendSettings):
  def __init__(self, package):
    super(WebviewShellBackendSettings, self).__init__(
        package=package,
        activity='org.chromium.android_webview.shell.AwShellActivity',
        command_line_name='android-webview-command-line',
        apk_name='WebViewInstrumentation.apk')


def _FindLocalApk(chrome_root, apk_name):
  found_apk_path = None
  found_last_changed = None
  for build_path in util.GetBuildDirectories(chrome_root):
    apk_path = os.path.join(build_path, 'apks', apk_name)
    if os.path.exists(apk_path):
      last_changed = os.path.getmtime(apk_path)
      # Keep the most recently updated apk only.
      if last_changed is None or last_changed > found_last_changed:
        found_apk_path = apk_path
        found_last_changed = last_changed

  return found_apk_path
