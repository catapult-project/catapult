# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import py_utils
from py_utils import exc_util

from telemetry.core import exceptions
from telemetry import decorators
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.backends.chrome import desktop_minidump_finder
from telemetry.internal.backends.chrome import misc_web_contents_backend
from telemetry.internal.util import binary_manager
from telemetry.internal.util import format_for_logging


# TODO(https://crbug.com/994274): Move the minidump symbolization code in this
# class into a separate class.
class CrOSBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  def __init__(self, cros_platform_backend, browser_options,
               browser_directory, profile_directory, is_guest, build_dir):
    assert browser_options.IsCrosBrowserOptions()
    super(CrOSBrowserBackend, self).__init__(
        cros_platform_backend,
        browser_options=browser_options,
        browser_directory=browser_directory,
        profile_directory=profile_directory,
        supports_extensions=not is_guest,
        supports_tab_control=True)
    self._is_guest = is_guest
    self._build_dir = build_dir
    self._cri = cros_platform_backend.cri
    self._dump_finder = None
    self._most_recent_symbolized_minidump_paths = set([])
    self._tmp_minidump_dir = tempfile.mkdtemp()

  @property
  def log_file_path(self):
    return None

  def _GetDevToolsActivePortPath(self):
    return '/home/chronos/DevToolsActivePort'

  def _FindDevToolsPortAndTarget(self):
    devtools_file_path = self._GetDevToolsActivePortPath()
    # GetFileContents may rise IOError or OSError, the caller will retry.
    lines = self._cri.GetFileContents(devtools_file_path).splitlines()
    if not lines:
      raise EnvironmentError('DevTools file empty')

    devtools_port = int(lines[0])
    browser_target = lines[1] if len(lines) >= 2 else None
    return devtools_port, browser_target

  def GetPid(self):
    return self._cri.GetChromePid()

  def __del__(self):
    self.Close()

  def Start(self, startup_args):
    self._cri.OpenConnection()
    # Remove the stale file with the devtools port / browser target
    # prior to restarting chrome.
    self._cri.RmRF(self._GetDevToolsActivePortPath())

    # DesktopMinidumpFinder is meant for Linux/Mac/Windows, but since dumps are
    # pulled off the emulator/device onto the host, and we only support Linux
    # hosts, we can use it as-is.
    # TODO(https://crbug.com/994274): Rename this class when minidump
    # symbolization code is consolidated.
    self._dump_finder = desktop_minidump_finder.DesktopMinidumpFinder(
        self.browser.platform.GetOSName(), self.browser.platform.GetArchName())

    # Escape all commas in the startup arguments we pass to Chrome
    # because dbus-send delimits array elements by commas
    startup_args = [a.replace(',', '\\,') for a in startup_args]

    # Restart Chrome with the login extension and remote debugging.
    pid = self.GetPid()
    logging.info('Restarting Chrome (pid=%d) with remote port', pid)
    args = ['dbus-send', '--system', '--type=method_call',
            '--dest=org.chromium.SessionManager',
            '/org/chromium/SessionManager',
            'org.chromium.SessionManagerInterface.EnableChromeTesting',
            'boolean:true',
            'array:string:"%s"' % ','.join(startup_args),
            'array:string:']
    formatted_args = format_for_logging.ShellFormat(
        args, trim=self.browser_options.trim_logs)
    logging.info('Starting Chrome: %s', formatted_args)
    self._cri.RunCmdOnDevice(args)

    # Wait for new chrome and oobe.
    py_utils.WaitFor(lambda: pid != self.GetPid(), 15)
    self.BindDevToolsClient()
    py_utils.WaitFor(lambda: self.oobe_exists, 30)

    if self.browser_options.auto_login:
      if self._is_guest:
        pid = self.GetPid()
        self.oobe.NavigateGuestLogin()
        # Guest browsing shuts down the current browser and launches an
        # incognito browser in a separate process, which we need to wait for.
        try:
          py_utils.WaitFor(lambda: pid != self.GetPid(), 15)

          # Also make sure we reconnect the devtools client to the new browser
          # process. It's important to do this before waiting for _IsLoggedIn,
          # otherwise the devtools connection check will still try to reach the
          # older DevTools agent (and fail to do so).
          self.BindDevToolsClient()
        except py_utils.TimeoutException:
          self._RaiseOnLoginFailure(
              'Failed to restart browser in guest mode (pid %d).' % pid)

      elif self.browser_options.gaia_login:
        self.oobe.NavigateGaiaLogin(self._username, self._password)
      else:
        # Wait for few seconds(the time of password typing) to have mini ARC
        # container up and running. Default is 0.
        time.sleep(self.browser_options.login_delay)
        # crbug.com/976983.
        retries = 3
        while True:
          try:
            self.oobe.NavigateFakeLogin(
                self._username, self._password, self._gaia_id,
                not self.browser_options.disable_gaia_services)
            break
          except py_utils.TimeoutException:
            logging.error('TimeoutException %d', retries)
            retries -= 1
            if not retries:
              raise

      try:
        self._WaitForLogin()
      except py_utils.TimeoutException:
        self._RaiseOnLoginFailure('Timed out going through login screen. '
                                  + self._GetLoginStatus())

    logging.info('Browser is up!')

  def Background(self):
    raise NotImplementedError

  @exc_util.BestEffort
  def Close(self):
    super(CrOSBrowserBackend, self).Close()

    if self._cri:
      self._cri.RestartUI(False) # Logs out.
      self._cri.CloseConnection()
      py_utils.WaitFor(lambda: not self._IsCryptohomeMounted(), 180)

    self._cri = None

    if self._tmp_minidump_dir:
      shutil.rmtree(self._tmp_minidump_dir, ignore_errors=True)
      self._tmp_minidump_dir = None

  def IsBrowserRunning(self):
    if not self._cri:
      return False
    return bool(self.GetPid())

  def GetStandardOutput(self):
    return 'Cannot get standard output on CrOS'

  def GetStackTrace(self):
    """Returns a stack trace if a valid minidump is found, will return a tuple
       (valid, output) where valid will be True if a valid minidump was found
       and output will contain either an error message or the attempt to
       symbolize the minidump if one was found.
    """
    most_recent_dump = self.GetMostRecentMinidumpPath()
    if not most_recent_dump:
      return (False, 'No crash dump found.')
    logging.info('Minidump found: %s', most_recent_dump)
    return self._InternalSymbolizeMinidump(most_recent_dump)

  def GetMostRecentMinidumpPath(self):
    self._cri.PullDumps(self._tmp_minidump_dir)
    dump_path, explanation = self._dump_finder.GetMostRecentMinidump(
        self._tmp_minidump_dir)
    logging.info('\n'.join(explanation))
    return dump_path

  def GetRecentMinidumpPathWithTimeout(self, timeout_s, oldest_ts):
    assert timeout_s > 0
    assert oldest_ts >= 0
    explanation = ['No explanation returned.']
    start_time = time.time()
    try:
      while time.time() - start_time < timeout_s:
        self._cri.PullDumps(self._tmp_minidump_dir)
        dump_path, explanation = self._dump_finder.GetMostRecentMinidump(
            self._tmp_minidump_dir)
        if not dump_path or os.path.getmtime(dump_path) < oldest_ts:
          continue
        return dump_path
      return None
    finally:
      logging.info('\n'.join(explanation))

  def GetAllMinidumpPaths(self):
    self._cri.PullDumps(self._tmp_minidump_dir)
    paths, explanation = self._dump_finder.GetAllMinidumpPaths(
        self._tmp_minidump_dir)
    logging.info('\n'.join(explanation))
    return paths

  def GetAllUnsymbolizedMinidumpPaths(self):
    minidump_paths = set(self.GetAllMinidumpPaths())
    # If we have already symbolized paths remove them from the list
    unsymbolized_paths = (
        minidump_paths - self._most_recent_symbolized_minidump_paths)
    return list(unsymbolized_paths)

  def SymbolizeMinidump(self, minidump_path):
    return self._SymbolizeMinidump(minidump_path)

  @property
  def supports_overview_mode(self): # pylint: disable=invalid-name
    return True

  def EnterOverviewMode(self, timeout):
    self.devtools_client.window_manager_backend.EnterOverviewMode(timeout)

  def ExitOverviewMode(self, timeout):
    self.devtools_client.window_manager_backend.ExitOverviewMode(timeout)

  @property
  @decorators.Cache
  def misc_web_contents_backend(self):
    """Access to chrome://oobe/login page."""
    return misc_web_contents_backend.MiscWebContentsBackend(self)

  @property
  def oobe(self):
    return self.misc_web_contents_backend.GetOobe()

  @property
  def oobe_exists(self):
    return self.misc_web_contents_backend.oobe_exists

  @property
  def _username(self):
    return self.browser_options.username

  @property
  def _password(self):
    return self.browser_options.password

  @property
  def _gaia_id(self):
    return self.browser_options.gaia_id

  def _IsCryptohomeMounted(self):
    username = '$guest' if self._is_guest else self._username
    return self._cri.IsCryptohomeMounted(username, self._is_guest)

  def _GetLoginStatus(self):
    """Returns login status. If logged in, empty string is returned."""
    status = ''
    if not self._IsCryptohomeMounted():
      status += 'Cryptohome not mounted. '
    if not self.HasDevToolsConnection():
      status += 'Browser didn\'t launch. '
    if self.oobe_exists:
      status += 'OOBE not dismissed.'
    return status

  def _IsLoggedIn(self):
    """Returns True if cryptohome has mounted, the browser is
    responsive to devtools requests, and the oobe has been dismissed."""
    return not self._GetLoginStatus()

  def _WaitForLogin(self):
    # Wait for cryptohome to mount.
    py_utils.WaitFor(self._IsLoggedIn, 900)

    # Wait for extensions to load.
    if self._supports_extensions:
      self._WaitForExtensionsToLoad()

  def _RaiseOnLoginFailure(self, error):
    if self._platform_backend.CanTakeScreenshot():
      self._cri.TakeScreenshotWithPrefix('login-screen')
    raise exceptions.LoginException(error)

  def _SymbolizeMinidump(self, minidump_path):
    """Symbolizes the given minidump.

    Args:
      minidump_path: the path to the minidump to symbolize

    Return:
      A tuple (valid, output). |valid| is True if the minidump was symbolized,
      otherwise False. |output| contains an error message if |valid| is False,
      otherwise it contains the symbolized minidump.
    """
    # TODO(https://crbug.com/994267): Make the minidump being symbolized
    # available as an artifact.
    stack = self._GetStackFromMinidump(minidump_path)
    if not stack:
      error_message = ('Failed to symbolize minidump.')
      return (False, error_message)

    self._most_recent_symbolized_minidump_paths.add(minidump_path)
    return (True, stack)

  def _GetStackFromMinidump(self, minidump):
    """Gets the stack trace from the given minidump.

    Args:
      minidump: the path to the minidump on disk

    Returns:
      None if the stack could not be retrieved for some reason, otherwise a
      string containing the stack trace.
    """
    if platform.system() != 'Linux' and platform.system() != 'Darwin':
      logging.warning('Cannot get stack traces unless running on a Posix host.')
      return None
    if not self._build_dir:
      logging.warning('Cannot get stack traces unless '
                      '--chromium-output-directory is specified.')
      return None

    os_name = 'linux'
    # TODO(https://crbug.com/994265): Figure out if this works on all host
    # architectures or if we need to create a mapping from Python architectures
    # to Telemetry architectures.
    arch_name = platform.machine()
    stackwalk = binary_manager.FetchPath(
        'minidump_stackwalk', arch_name, os_name)
    if not stackwalk:
      logging.warning('minidump_stackwalk binary not found.')
      return None
    if not self._dump_finder.MinidumpObtainedFromCrashpad(minidump):
      with open(minidump, 'rb') as infile:
        minidump += '.stripped'
        with open(minidump, 'wb') as outfile:
          outfile.write(''.join(infile.read().partition('MDMP')[1:]))

    symbols_path = os.path.join(self._tmp_minidump_dir, 'symbols')
    GenerateBreakpadSymbols(arch_name, os_name,
                            symbols_path, self._build_dir)

    return subprocess.check_output([stackwalk, minidump, symbols_path],
                                   stderr=open(os.devnull, 'w'))


def GenerateBreakpadSymbols(arch, os_name, symbols_dir, build_dir):
  """Generates Breakpad symbols for the given build directory.

  Args:
    arch: the architecture of the host, used to find dependencies
    os_name: the OS of the host, used to find dependencies
    symbols_dir: the directory where Breakpad symbols will be dumped to
    build_dir: the directory containing Chromium build artifacts to generate
        symbols from.
  """
  logging.info('Dumping breakpad symbols.')
  generate_breakpad_symbols_command = binary_manager.FetchPath(
      'generate_breakpad_symbols', arch, os_name)
  if not generate_breakpad_symbols_command:
    logging.warning('generate_breakpad_symbols binary not found')
    return

  cmd = [
      sys.executable,
      generate_breakpad_symbols_command,
      '--binary=%s' % os.path.join(build_dir, 'chrome'),
      '--symbols-dir=%s' % symbols_dir,
      '--build-dir=%s' % build_dir,
      # TODO(https://crbug.com/978952): Switch this to chromeos once support
      # has been added to generate_breakpad_symbols. Not passing anything causes
      # it to use ldd to get shared library dependencies, which has trouble
      # with running on 32-bit binaries on a 64-bit host, or vice-versa.
      # Specifying Android makes it use readelf instead, which works fine with
      # mixed bitness, and still works for x86-based binaries, e.g. when run
      # against the amd64-generic board.
      '--platform=android',
      ]

  try:
    subprocess.check_output(cmd)
  except subprocess.CalledProcessError as e:
    logging.error(e.output)
    logging.warning('Failed to execute "%s"', ' '.join(cmd))
    return


