# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions
from telemetry.internal.platform import android_platform_backend as \
  android_platform_backend_module
from telemetry.internal.backends import browser_backend
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.browser import user_agent

from devil.android import app_ui
from devil.android import device_signal
from devil.android import flag_changer
from devil.android.sdk import intent


class AndroidBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a browser instance running on Android."""
  def __init__(self, android_platform_backend, browser_options,
               backend_settings):
    assert isinstance(android_platform_backend,
                      android_platform_backend_module.AndroidPlatformBackend)
    super(AndroidBrowserBackend, self).__init__(
        android_platform_backend,
        supports_tab_control=backend_settings.supports_tab_control,
        supports_extensions=False, browser_options=browser_options)

    extensions_to_load = browser_options.extensions_to_load

    if len(extensions_to_load) > 0:
      raise browser_backend.ExtensionsNotSupportedException(
          'Android browser does not support extensions.')

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._backend_settings = backend_settings
    self._saved_sslflag = ''
    self._app_ui = None
    self._profile_directory = None

    # Set the debug app if needed.
    self.platform_backend.SetDebugApp(self._backend_settings.package)

  @property
  def log_file_path(self):
    return None

  @property
  def device(self):
    return self.platform_backend.device

  @property
  def supports_app_ui_interactions(self):
    return True

  def GetAppUi(self):
    if self._app_ui is None:
      self._app_ui = app_ui.AppUi(self.device, package=self.package)
    return self._app_ui

  def _StopBrowser(self):
    # Note: it's important to stop and _not_ kill the browser app, since
    # stopping also clears the app state in Android's activity manager.
    self.platform_backend.StopApplication(self._backend_settings.package)

  def _SetupProfile(self):
    if self.browser_options.dont_override_profile:
      return
    if self.browser_options.profile_dir:
      self.platform_backend.PushProfile(
          self._backend_settings.package,
          self.browser_options.profile_dir)
    else:
      self.platform_backend.RemoveProfile(
          self._backend_settings.package,
          self._backend_settings.profile_ignore_list)

  def _CollectProfile(self):
    if self._output_profile_path:
      self.platform_backend.PullProfile(
          self._backend_settings.package, self._output_profile_path)

  def Start(self, startup_args, startup_url=None):
    self.device.adb.Logcat(clear=True)
    self.platform_backend.DismissCrashDialogIfNeeded()
    user_agent_dict = user_agent.GetChromeUserAgentDictFromType(
        self.browser_options.browser_user_agent_type)
    command_line_name = self._backend_settings.command_line_name
    with flag_changer.CustomCommandLineFlags(
        self.device, command_line_name, startup_args):
      # Stop existing browser, if any. This is done *after* setting the
      # command line flags, in case some other Android process manages to
      # trigger Chrome's startup before we do.
      self._StopBrowser()
      self._SetupProfile()
      self.device.StartActivity(
          intent.Intent(package=self._backend_settings.package,
                        activity=self._backend_settings.activity,
                        action=None, data=startup_url, category=None,
                        extras=user_agent_dict),
          blocking=True)

      try:
        self.BindDevToolsClient()
      except:
        self.Close()
        raise

  def _FindDevToolsPortAndTarget(self):
    devtools_port = self._backend_settings.GetDevtoolsRemotePort(self.device)
    browser_target = None  # Use default
    return devtools_port, browser_target

  def Foreground(self):
    package = self._backend_settings.package
    activity = self._backend_settings.activity
    self.device.StartActivity(
        intent.Intent(package=package,
                      activity=activity,
                      action=None,
                      flags=[intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED]),
        blocking=False)
    # TODO(crbug.com/601052): The following waits for any UI node for the
    # package launched to appear on the screen. When the referenced bug is
    # fixed, remove this workaround and just switch blocking above to True.
    try:
      app_ui.AppUi(self.device).WaitForUiNode(package=package)
    except Exception:
      raise exceptions.BrowserGoneException(
          self.browser,
          'Timed out waiting for browser to come back foreground.')

  def Background(self):
    package = 'org.chromium.push_apps_to_background'
    activity = package + '.PushAppsToBackgroundActivity'
    self.device.StartActivity(
        intent.Intent(
            package=package,
            activity=activity,
            action=None,
            flags=[intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED]),
        blocking=True)

  def GetBrowserStartupArgs(self):
    # TODO(crbug.com/787834): Move to the corresponding possible-browser class.
    args = super(AndroidBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--enable-remote-debugging')
    args.append('--disable-fre')
    args.append('--disable-external-intent-requests')
    # Specifies the user profile directory, a prerequisite for
    # --ignore-certificate-errors-spki-list, which allows Chrome to selectively
    # bypass cert errors while exercising HTTP disk cache and avoiding
    # re-establishing socket connections.
    args.append('--user-data-dir=' + self.profile_directory)
    return args

  def GetBrowserStartupUrl(self):
    # TODO(crbug.com/787834): Move to the corresponding possible-browser class.
    if self.browser_options.startup_url:
      return self.browser_options.startup_url
    elif self.browser_options.profile_dir:
      return None
    else:
      # If we have no existing tabs start with a blank page since default
      # startup with the NTP can lead to race conditions with Telemetry
      return 'about:blank'

  def ForceJavaHeapGarbageCollection(self):
    # Send USR1 signal to force GC on Chrome processes forked from Zygote.
    # (c.f. crbug.com/724032)
    self.device.KillAll(
        self._backend_settings.package,
        exact=False,  # Send signal to children too.
        signum=device_signal.SIGUSR1)

  @property
  def pid(self):
    try:
      # Although there might be multiple processes sharing the same name as
      # the browser app, the browser process is the only one being a direct
      # descendant of an Android zygote. (See crbug.com/785446)
      zygotes = self.device.ListProcesses('zygote')
      zygote_pids = set(p.pid for p in zygotes)
      assert zygote_pids, 'No Android zygote found'

      processes = self.device.ListProcesses(self._backend_settings.package)
      pids = []
      for process in processes:
        if (process.name == self._backend_settings.package and
            process.ppid in zygote_pids):
          pids.append(process.pid)
      assert len(pids) <= 1, 'Found too many browsers: %r' % pids
    except Exception as exc:
      # Re-raise as an AppCrashException to get further diagnostic information.
      # In particular we also get the values of all local variables above.
      raise exceptions.AppCrashException(
          self.browser, 'Error getting browser PID: %s' % exc)
    if not pids:
      raise exceptions.BrowserGoneException(self.browser)
    return pids[0]

  @property
  def browser_directory(self):
    return None

  @property
  def profile_directory(self):
    if not self._profile_directory:
      self._profile_directory = (
          self.platform_backend.GetProfileDir(self._backend_settings.package))
    return self._profile_directory

  @property
  def package(self):
    return self._backend_settings.package

  @property
  def activity(self):
    return self._backend_settings.activity

  def __del__(self):
    self.Close()

  def Close(self):
    super(AndroidBrowserBackend, self).Close()
    self._StopBrowser()
    self._CollectProfile()

  def IsBrowserRunning(self):
    return self.platform_backend.IsAppRunning(self._backend_settings.package)

  def GetStandardOutput(self):
    return self.platform_backend.GetStandardOutput()

  def GetStackTrace(self):
    return self.platform_backend.GetStackTrace()

  def GetMostRecentMinidumpPath(self):
    return None

  def GetAllMinidumpPaths(self):
    return None

  def GetAllUnsymbolizedMinidumpPaths(self):
    return None

  def SymbolizeMinidump(self, minidump_path):
    return None
