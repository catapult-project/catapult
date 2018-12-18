# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds android browsers that can be started and controlled by telemetry."""

import contextlib
import logging
import os
import shutil
import subprocess
import sys

from devil import base_error
from devil.android import apk_helper
from devil.android import flag_changer
from py_utils import dependency_util
from py_utils import file_util
from py_utils import tempfile_ext
from telemetry import compact_mode_options
from telemetry import decorators
from telemetry.core import exceptions
from telemetry.core import platform
from telemetry.internal.backends import android_browser_backend_settings
from telemetry.internal.backends.chrome import android_browser_backend
from telemetry.internal.backends.chrome import chrome_startup_args
from telemetry.internal.backends.chrome import gpu_compositing_checker
from telemetry.internal.browser import browser
from telemetry.internal.browser import possible_browser
from telemetry.internal.platform import android_device
from telemetry.internal.util import binary_manager


ANDROID_BACKEND_SETTINGS = (
    android_browser_backend_settings.ANDROID_BACKEND_SETTINGS)


@contextlib.contextmanager
def _ProfileWithExtraFiles(profile_dir, profile_files_to_copy):
  """Yields a temporary directory populated with input files.

  Args:
    profile_dir: A directory whose contents will be copied to the output
      directory.
    profile_files_to_copy: A list of (source, dest) tuples to be copied to
      the output directory.

  Yields: A path to a temporary directory, named "_default_profile". This
    directory will be cleaned up when this context exits.
  """
  with tempfile_ext.NamedTemporaryDirectory() as tempdir:
    # TODO(csharrison): "_default_profile" was chosen because this directory
    # will be pushed to the device's sdcard. We don't want to choose a
    # random name due to the extra failure mode of filling up the sdcard
    # in the case of unclean test teardown. We should consider changing
    # PushProfile to avoid writing to this intermediate location.
    host_profile = os.path.join(tempdir, '_default_profile')
    if profile_dir:
      shutil.copytree(profile_dir, host_profile)
    else:
      os.mkdir(host_profile)

    # Add files from |profile_files_to_copy| into the host profile
    # directory. Don't copy files if they already exist.
    for source, dest in profile_files_to_copy:
      host_path = os.path.join(host_profile, dest)
      if not os.path.exists(host_path):
        file_util.CopyFileWithIntermediateDirectories(source, host_path)
    yield host_profile


class PossibleAndroidBrowser(possible_browser.PossibleBrowser):
  """A launchable android browser instance."""

  def __init__(self, browser_type, finder_options, android_platform,
               backend_settings, local_apk=None):
    super(PossibleAndroidBrowser, self).__init__(
        browser_type, 'android', backend_settings.supports_tab_control)
    assert browser_type in FindAllBrowserTypes(finder_options), (
        'Please add %s to android_browser_finder.FindAllBrowserTypes' %
        browser_type)
    self._platform = android_platform
    self._platform_backend = (
        android_platform._platform_backend)  # pylint: disable=protected-access
    self._backend_settings = backend_settings
    self._local_apk = local_apk
    self._flag_changer = None

    if self._local_apk is None and finder_options.chrome_root is not None:
      self._local_apk = self._backend_settings.FindLocalApk(
          self._platform_backend.device, finder_options.chrome_root)

    # At this point the local_apk, if any, must exist.
    assert self._local_apk is None or os.path.exists(self._local_apk)

    self._embedder_apk = None
    if self._backend_settings.requires_embedder:
      if finder_options.webview_embedder_apk:
        self._embedder_apk = finder_options.webview_embedder_apk
      else:
        self._embedder_apk = self._backend_settings.FindEmbedderApk(
            self._local_apk, finder_options.chrome_root)
    elif finder_options.webview_embedder_apk:
      logging.warning(
          'No embedder needed for %s, ignoring --webview-embedder-apk option',
          self._backend_settings.browser_type)

    # At this point the embedder_apk, if any, must exist.
    assert self._embedder_apk is None or os.path.exists(self._embedder_apk)

  def __repr__(self):
    return 'PossibleAndroidBrowser(browser_type=%s)' % self.browser_type

  @property
  def settings(self):
    """Get the backend_settings for this possible browser."""
    return self._backend_settings

  @property
  def browser_directory(self):
    # On Android L+ the directory where base APK resides is also used for
    # keeping extracted native libraries and .odex. Here is an example layout:
    # /data/app/$package.apps.chrome-1/
    #                                  base.apk
    #                                  lib/arm/libchrome.so
    #                                  oat/arm/base.odex
    # Declaring this toplevel directory as 'browser_directory' allows the cold
    # startup benchmarks to flush OS pagecache for the native library, .odex and
    # the APK.
    apks = self._platform_backend.device.GetApplicationPaths(
        self._backend_settings.package)
    # A package can map to multiple APKs iff the package overrides the app on
    # the system image. Such overrides should not happen on perf bots.
    assert len(apks) == 1
    base_apk = apks[0]
    if not base_apk or not base_apk.endswith('/base.apk'):
      return None
    return base_apk[:-9]

  @property
  def profile_directory(self):
    return self._platform_backend.GetProfileDir(self._backend_settings.package)

  @property
  def last_modification_time(self):
    if self._local_apk:
      return os.path.getmtime(self._local_apk)
    return -1

  def _GetPathsForOsPageCacheFlushing(self):
    paths_to_flush = [self.profile_directory]
    # On N+ the Monochrome is the most widely used configuration. Since Webview
    # is used often, the typical usage is closer to have the DEX and the native
    # library be resident in memory. Skip the pagecache flushing for browser
    # directory on N+.
    if self._platform_backend.device.build_version_sdk < 24:
      paths_to_flush.append(self.browser_directory)
    return paths_to_flush

  def _InitPlatformIfNeeded(self):
    pass

  def _SetupProfile(self):
    if self._browser_options.dont_override_profile:
      return

    # Just remove the existing profile if we don't have any files to copy over.
    # This is because PushProfile does not support pushing completely empty
    # directories.
    profile_files_to_copy = self._browser_options.profile_files_to_copy
    if not self._browser_options.profile_dir and not profile_files_to_copy:
      self._platform_backend.RemoveProfile(
          self._backend_settings.package,
          self._backend_settings.profile_ignore_list)
      return

    with _ProfileWithExtraFiles(self._browser_options.profile_dir,
                                profile_files_to_copy) as profile_dir:
      self._platform_backend.PushProfile(self._backend_settings.package,
                                         profile_dir)

  def SetUpEnvironment(self, browser_options):
    super(PossibleAndroidBrowser, self).SetUpEnvironment(browser_options)
    self._platform_backend.DismissCrashDialogIfNeeded()
    device = self._platform_backend.device
    startup_args = self.GetBrowserStartupArgs(self._browser_options)
    device.adb.Logcat(clear=True)

    # use legacy commandline path if in compatibility mode
    self._flag_changer = flag_changer.FlagChanger(
        device, self._backend_settings.command_line_name, use_legacy_path=
        compact_mode_options.LEGACY_COMMAND_LINE_PATH in
        browser_options.compatibility_mode)
    self._flag_changer.ReplaceFlags(startup_args)
    # Stop any existing browser found already running on the device. This is
    # done *after* setting the command line flags, in case some other Android
    # process manages to trigger Chrome's startup before we do.
    self._platform_backend.StopApplication(self._backend_settings.package)
    self._SetupProfile()

  def _TearDownEnvironment(self):
    self._RestoreCommandLineFlags()

  def _RestoreCommandLineFlags(self):
    if self._flag_changer is not None:
      try:
        self._flag_changer.Restore()
      finally:
        self._flag_changer = None

  def _GetBrowserStartupUrl(self):
    if self._browser_options.startup_url:
      return self._browser_options.startup_url
    elif self._browser_options.profile_dir:
      return None
    else:
      # If we have no existing tabs start with a blank page since default
      # startup with the NTP can lead to race conditions with Telemetry
      return 'about:blank'

  def Create(self, clear_caches=True):
    """Launch the browser on the device and return a Browser object."""
    return self._GetBrowserInstance(
        existing=False, clear_caches=clear_caches,
        startup_url=self._GetBrowserStartupUrl())

  def FindExistingBrowser(self):
    """Find a browser running on the device and bind a Browser object to it.

    The returned Browser object will only be bound to a running browser
    instance whose package name matches the one specified by the backend
    settings of this possible browser.

    A BrowserGoneException is raised if the browser cannot be found.
    """
    return self._GetBrowserInstance(existing=True, clear_caches=False)

  def _GetBrowserInstance(self, existing, clear_caches, startup_url=None):
    browser_backend = android_browser_backend.AndroidBrowserBackend(
        self._platform_backend, self._browser_options,
        self.browser_directory, self.profile_directory,
        self._backend_settings)
    # TODO(crbug.com/811244): Remove when this is handled by shared state.
    if clear_caches:
      self._ClearCachesOnStart()
    try:
      returned_browser = browser.Browser(
          browser_backend, self._platform_backend, startup_args=(),
          startup_url=startup_url, find_existing=existing)
      # TODO(crbug.com/916086): Move this assertion to callers.
      if self._browser_options.assert_gpu_compositing:
        gpu_compositing_checker.AssertGpuCompositingEnabled(
            returned_browser.GetSystemInfo())
      return returned_browser
    except Exception:
      exc_info = sys.exc_info()
      logging.error(
          'Failed with %s while creating Android browser.',
          exc_info[0].__name__)
      try:
        browser_backend.Close()
      except Exception:  # pylint: disable=broad-except
        logging.exception('Secondary failure while closing browser backend.')

      raise exc_info[0], exc_info[1], exc_info[2]

  def GetBrowserStartupArgs(self, browser_options):
    startup_args = chrome_startup_args.GetFromBrowserOptions(browser_options)
    # use the flag `--ignore-certificate-errors` if in compatibility mode
    supports_spki_list = (
        self._backend_settings.supports_spki_list and
        compact_mode_options.IGNORE_CERTIFICATE_ERROR
        not in browser_options.compatibility_mode)
    startup_args.extend(chrome_startup_args.GetReplayArgs(
        self._platform_backend.network_controller_backend,
        supports_spki_list=supports_spki_list))
    startup_args.append('--enable-remote-debugging')
    startup_args.append('--disable-fre')
    startup_args.append('--disable-external-intent-requests')

    # Need to specify the user profile directory for
    # --ignore-certificate-errors-spki-list to work.
    startup_args.append('--user-data-dir=' + self.profile_directory)

    return startup_args

  def SupportsOptions(self, browser_options):
    if len(browser_options.extensions_to_load) != 0:
      return False
    return True

  def IsAvailable(self):
    """Returns True if the browser is or can be installed on the platform."""
    has_local_apks = self._local_apk and (
        not self._backend_settings.requires_embedder or self._embedder_apk)
    return has_local_apks or self.platform.CanLaunchApplication(
        self.settings.package)

  @decorators.Cache
  def UpdateExecutableIfNeeded(self):
    # TODO(crbug.com/815133): This logic should belong to backend_settings.
    if self._local_apk:
      logging.warn('Installing %s on device if needed.', self._local_apk)
      self.platform.InstallApplication(self._local_apk)

    if self._embedder_apk:
      logging.warn('Installing %s on device if needed.', self._embedder_apk)
      self.platform.InstallApplication(self._embedder_apk)

    if (self._backend_settings.GetApkName(
        self._platform_backend.device) == 'Monochrome.apk'):
      self._platform_backend.device.SetWebViewImplementation(
          android_browser_backend_settings.ANDROID_CHROME.package)


def SelectDefaultBrowser(possible_browsers):
  """Return the newest possible browser."""
  if not possible_browsers:
    return None
  return max(possible_browsers, key=lambda b: b.last_modification_time)


def CanFindAvailableBrowsers():
  return android_device.CanDiscoverDevices()


def _CanPossiblyHandlePath(apk_path):
  return apk_path and apk_path[-4:].lower() == '.apk'


def FindAllBrowserTypes(options):
  del options  # unused
  browser_types = [b.browser_type for b in ANDROID_BACKEND_SETTINGS]
  return browser_types + ['exact', 'reference']


def _FindAllPossibleBrowsers(finder_options, android_platform):
  """Testable version of FindAllAvailableBrowsers."""
  if not android_platform:
    return []
  possible_browsers = []

  if finder_options.webview_embedder_apk and not os.path.exists(
      finder_options.webview_embedder_apk):
    raise exceptions.PathMissingError(
        'Unable to find apk specified by --webview-embedder-apk=%s' %
        finder_options.browser_executable)

  # Add the exact APK if given.
  if _CanPossiblyHandlePath(finder_options.browser_executable):
    if not os.path.exists(finder_options.browser_executable):
      raise exceptions.PathMissingError(
          'Unable to find exact apk specified by --browser-executable=%s' %
          finder_options.browser_executable)

    package_name = apk_helper.GetPackageName(finder_options.browser_executable)
    try:
      backend_settings = next(
          b for b in ANDROID_BACKEND_SETTINGS if b.package == package_name)
    except StopIteration:
      raise exceptions.UnknownPackageError(
          '%s specified by --browser-executable has an unknown package: %s' %
          (finder_options.browser_executable, package_name))

    possible_browsers.append(PossibleAndroidBrowser(
        'exact',
        finder_options,
        android_platform,
        backend_settings,
        finder_options.browser_executable))

  # Add the reference build if found.
  os_version = dependency_util.GetChromeApkOsVersion(
      android_platform.GetOSVersionName())
  arch = android_platform.GetArchName()
  try:
    reference_build = binary_manager.FetchPath(
        'chrome_stable', arch, 'android', os_version)
  except (binary_manager.NoPathFoundError,
          binary_manager.CloudStorageError):
    reference_build = None

  if reference_build and os.path.exists(reference_build):
    # TODO(aiolos): how do we stably map the android chrome_stable apk to the
    # correct backend settings?
    possible_browsers.append(PossibleAndroidBrowser(
        'reference',
        finder_options,
        android_platform,
        android_browser_backend_settings.ANDROID_CHROME,
        reference_build))

  # Add any other known available browsers.
  for settings in ANDROID_BACKEND_SETTINGS:
    p_browser = PossibleAndroidBrowser(
        settings.browser_type, finder_options, android_platform, settings)
    if p_browser.IsAvailable():
      possible_browsers.append(p_browser)
  return possible_browsers


def FindAllAvailableBrowsers(finder_options, device):
  """Finds all the possible browsers on one device.

  The device is either the only device on the host platform,
  or |finder_options| specifies a particular device.
  """
  if not isinstance(device, android_device.AndroidDevice):
    return []

  try:
    android_platform = platform.GetPlatformForDevice(device, finder_options)
    return _FindAllPossibleBrowsers(finder_options, android_platform)
  except base_error.BaseError as e:
    logging.error('Unable to find browsers on %s: %s', device.device_id, str(e))
    ps_output = subprocess.check_output(['ps', '-ef'])
    logging.error('Ongoing processes:\n%s', ps_output)
  return []
