# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import glob
import heapq
import logging
import os
import os.path
import random
import re
import shutil
import subprocess as subprocess
import sys
import tempfile
import time

from catapult_base import cloud_storage  # pylint: disable=import-error


from telemetry.internal.util import binary_manager
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.internal.backends import browser_backend
from telemetry.internal.backends.chrome import chrome_browser_backend
from telemetry.internal.util import path


def ParseCrashpadDateTime(date_time_str):
  # Python strptime does not support time zone parsing, strip it.
  date_time_parts = date_time_str.split()
  if len(date_time_parts) >= 3:
    date_time_str = ' '.join(date_time_parts[:2])
  return datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')


def GetSymbolBinaries(executable, os_name):
  # Returns binary file where symbols are located.
  if os_name == 'mac':
    executables = []
    version_dir = os.path.abspath(os.path.join(os.path.dirname(executable),
                                  '..',
                                  'Versions'))

    # Add possible executable files.
    for version_num in os.listdir(version_dir):
      version_num_dir = os.path.join(version_dir, version_num)
      possible_files = [os.path.join(version_num_dir,
                                     'Chromium Framework.framework',
                                     'Chromium Framework'),
                        os.path.join(version_num_dir,
                                     'Chromium Helper.app',
                                     'Contents',
                                     'MacOS',
                                     'Chromium Helper')]
      executables.extend([file_path
                          for file_path in possible_files
                          if os.path.isfile(file_path)])

    # Add possible dynamic library files.
    output_dir = os.path.abspath(os.path.join(version_dir, '..', '..', '..'))
    executables.extend([os.path.join(output_dir, filename)
                        for filename in os.listdir(output_dir)
                        if filename.endswith('.dylib')])

    # Sometimes dyld returns symbols for a different file. Emulate what it
    # does here by using the same mechanism to find the binary file.
    def GetDyldPath(file_path):
      import fcntl
      F_GETPATH = 50
      with open(file_path, 'rb') as f:
        path2 = fcntl.fcntl(f.fileno(), F_GETPATH, b'\0' * 1024).rstrip(b'\0')
      if os.path.isfile(path2):
        return path2
      return file_path
    return [GetDyldPath(file_path) for file_path in executables]

  return [executable]


class DesktopBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a locally-executed browser instance, on Linux,
  Mac or Windows.
  """
  def __init__(self, desktop_platform_backend, browser_options, executable,
               flash_path, is_content_shell, browser_directory,
               output_profile_path, extensions_to_load):
    super(DesktopBrowserBackend, self).__init__(
        desktop_platform_backend,
        supports_tab_control=not is_content_shell,
        supports_extensions=not is_content_shell,
        browser_options=browser_options,
        output_profile_path=output_profile_path,
        extensions_to_load=extensions_to_load)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._proc = None
    self._tmp_profile_dir = None
    self._tmp_output_file = None

    self._executable = executable
    if not self._executable:
      raise Exception('Cannot create browser, no executable found!')

    assert not flash_path or os.path.exists(flash_path)
    self._flash_path = flash_path

    self._is_content_shell = is_content_shell

    if len(extensions_to_load) > 0 and is_content_shell:
      raise browser_backend.ExtensionsNotSupportedException(
          'Content shell does not support extensions.')

    self._browser_directory = browser_directory
    self._port = None
    self._tmp_minidump_dir = tempfile.mkdtemp()
    self._crash_service = None
    if self.browser_options.enable_logging:
      self._log_file_path = os.path.join(tempfile.mkdtemp(), 'chrome.log')
    else:
      self._log_file_path = None

    self._SetupProfile()

  @property
  def log_file_path(self):
    return self._log_file_path

  @property
  def supports_uploading_logs(self):
    return (self.browser_options.logs_cloud_bucket and self.log_file_path and
            os.path.isfile(self.log_file_path))

  def _SetupProfile(self):
    if not self.browser_options.dont_override_profile:
      if self._output_profile_path:
        self._tmp_profile_dir = self._output_profile_path
      else:
        self._tmp_profile_dir = tempfile.mkdtemp()

      profile_dir = self.browser_options.profile_dir
      if profile_dir:
        assert self._tmp_profile_dir != profile_dir
        if self._is_content_shell:
          logging.critical('Profiles cannot be used with content shell')
          sys.exit(1)
        logging.info("Using profile directory:'%s'." % profile_dir)
        shutil.rmtree(self._tmp_profile_dir)
        shutil.copytree(profile_dir, self._tmp_profile_dir)
    # No matter whether we're using an existing profile directory or
    # creating a new one, always delete the well-known file containing
    # the active DevTools port number.
    port_file = self._GetDevToolsActivePortPath()
    if os.path.isfile(port_file):
      try:
        os.remove(port_file)
      except Exception as e:
        logging.critical('Unable to remove DevToolsActivePort file: %s' % e)
        sys.exit(1)

  def _GetDevToolsActivePortPath(self):
    return os.path.join(self.profile_directory, 'DevToolsActivePort')

  def _GetCrashServicePipeName(self):
    # Ensure a unique pipe name by using the name of the temp dir.
    pipe = r'\\.\pipe\%s_service' % os.path.basename(self._tmp_minidump_dir)
    return pipe

  def _StartCrashService(self):
    os_name = self.browser.platform.GetOSName()
    if os_name != 'win':
      return None
    arch_name = self.browser.platform.GetArchName()
    command = binary_manager.FetchPath('crash_service', arch_name, os_name)
    if not command:
      logging.warning('crash_service.exe not found for %s %s',
                      arch_name, os_name)
      return None
    if not os.path.exists(command):
      logging.warning('crash_service.exe not found for %s %s',
                      arch_name, os_name)
      return None

    try:
      crash_service = subprocess.Popen([
          command,
          '--no-window',
          '--dumps-dir=%s' % self._tmp_minidump_dir,
          '--pipe-name=%s' % self._GetCrashServicePipeName()])
    except Exception:
      logging.error(
          'Failed to run %s --no-window --dump-dir=%s --pip-name=%s' % (
            command, self._tmp_minidump_dir, self._GetCrashServicePipeName()))
      logging.error('Running on platform: %s and arch: %s.', os_name, arch_name)
      wmic_stdout, _ = subprocess.Popen(
        ['wmic', 'process', 'get', 'CommandLine,Name,ProcessId,ParentProcessId',
        '/format:csv'], stdout=subprocess.PIPE).communicate()
      logging.error('Current running processes:\n%s' % wmic_stdout)
      raise
    return crash_service

  def _GetCdbPath(self):
    possible_paths = (
        'Debugging Tools For Windows',
        'Debugging Tools For Windows (x86)',
        'Debugging Tools For Windows (x64)',
        os.path.join('Windows Kits', '8.0', 'Debuggers', 'x86'),
        os.path.join('Windows Kits', '8.0', 'Debuggers', 'x64'),
        os.path.join('win_toolchain', 'vs2013_files', 'win8sdk', 'Debuggers',
                     'x86'),
        os.path.join('win_toolchain', 'vs2013_files', 'win8sdk', 'Debuggers',
                     'x64'),
    )
    for possible_path in possible_paths:
      app_path = os.path.join(possible_path, 'cdb.exe')
      app_path = path.FindInstalledWindowsApplication(app_path)
      if app_path:
        return app_path
    return None

  def HasBrowserFinishedLaunching(self):
    # In addition to the functional check performed by the base class, quickly
    # check if the browser process is still alive.
    if not self.IsBrowserRunning():
      raise exceptions.ProcessGoneException(
          "Return code: %d" % self._proc.returncode)
    # Start DevTools on an ephemeral port and wait for the well-known file
    # containing the port number to exist.
    port_file = self._GetDevToolsActivePortPath()
    if not os.path.isfile(port_file):
      # File isn't ready yet. Return false. Will retry.
      return False
    # Attempt to avoid reading the file until it's populated.
    got_port = False
    try:
      if os.stat(port_file).st_size > 0:
        with open(port_file) as f:
          port_string = f.read()
          self._port = int(port_string)
          logging.info('Discovered ephemeral port %s' % self._port)
          got_port = True
    except Exception:
      # Both stat and open can throw exceptions.
      pass
    if not got_port:
      # File isn't ready yet. Return false. Will retry.
      return False
    return super(DesktopBrowserBackend, self).HasBrowserFinishedLaunching()

  def GetBrowserStartupArgs(self):
    args = super(DesktopBrowserBackend, self).GetBrowserStartupArgs()
    self._port = 0
    logging.info('Requested remote debugging port: %d' % self._port)
    args.append('--remote-debugging-port=%i' % self._port)
    args.append('--enable-crash-reporter-for-testing')
    if not self._is_content_shell:
      args.append('--window-size=1280,1024')
      if self._flash_path:
        args.append('--ppapi-flash-path=%s' % self._flash_path)
      if not self.browser_options.dont_override_profile:
        args.append('--user-data-dir=%s' % self._tmp_profile_dir)
    else:
      args.append('--data-path=%s' % self._tmp_profile_dir)

    trace_config_file = (self.platform_backend.tracing_controller_backend
                         .GetChromeTraceConfigFile())
    if trace_config_file:
      args.append('--trace-config-file=%s' % trace_config_file)
    return args

  def Start(self):
    assert not self._proc, 'Must call Close() before Start()'

    args = [self._executable]
    args.extend(self.GetBrowserStartupArgs())
    if self.browser_options.startup_url:
      args.append(self.browser_options.startup_url)
    env = os.environ.copy()
    env['CHROME_HEADLESS'] = '1'  # Don't upload minidumps.
    env['BREAKPAD_DUMP_LOCATION'] = self._tmp_minidump_dir
    env['CHROME_BREAKPAD_PIPE_NAME'] = self._GetCrashServicePipeName()
    if self.browser_options.enable_logging:
      sys.stderr.write(
        'Chrome log file will be saved in %s\n' % self.log_file_path)
      env['CHROME_LOG_FILE'] = self.log_file_path
    self._crash_service = self._StartCrashService()
    logging.info('Starting Chrome %s', args)
    if not self.browser_options.show_stdout:
      self._tmp_output_file = tempfile.NamedTemporaryFile('w', 0)
      self._proc = subprocess.Popen(
          args, stdout=self._tmp_output_file, stderr=subprocess.STDOUT, env=env)
    else:
      self._proc = subprocess.Popen(args, env=env)

    try:
      self._WaitForBrowserToComeUp()
      # browser is foregrounded by default on Windows and Linux, but not Mac.
      if self.browser.platform.GetOSName() == 'mac':
        subprocess.Popen([
          'osascript', '-e', ('tell application "%s" to activate' %
                              self._executable)])
      self._InitDevtoolsClientBackend()
      if self._supports_extensions:
        self._WaitForExtensionsToLoad()
    except:
      self.Close()
      raise

  @property
  def pid(self):
    if self._proc:
      return self._proc.pid
    return None

  @property
  def browser_directory(self):
    return self._browser_directory

  @property
  def profile_directory(self):
    return self._tmp_profile_dir

  def IsBrowserRunning(self):
    return self._proc and self._proc.poll() == None

  def GetStandardOutput(self):
    if not self._tmp_output_file:
      if self.browser_options.show_stdout:
        # This can happen in the case that loading the Chrome binary fails.
        # We print rather than using logging here, because that makes a
        # recursive call to this function.
        print >> sys.stderr, "Can't get standard output with --show-stdout"
      return ''
    self._tmp_output_file.flush()
    try:
      with open(self._tmp_output_file.name) as f:
        return f.read()
    except IOError:
      return ''

  def _GetMostRecentCrashpadMinidump(self):
    os_name = self.browser.platform.GetOSName()
    arch_name = self.browser.platform.GetArchName()
    crashpad_database_util = binary_manager.FetchPath(
        'crashpad_database_util', arch_name, os_name)
    if not crashpad_database_util:
      return None

    report_output = subprocess.check_output([
        crashpad_database_util, '--database=' + self._tmp_minidump_dir,
        '--show-pending-reports', '--show-completed-reports',
        '--show-all-report-info'])

    last_indentation = -1
    reports_list = []
    report_dict = {}
    for report_line in report_output.splitlines():
      # Report values are grouped together by the same indentation level.
      current_indentation = 0
      for report_char in report_line:
        if not report_char.isspace():
          break
        current_indentation += 1

      # Decrease in indentation level indicates a new report is being printed.
      if current_indentation >= last_indentation:
        report_key, report_value = report_line.split(':', 1)
        if report_value:
          report_dict[report_key.strip()] = report_value.strip()
      elif report_dict:
        try:
          report_time = ParseCrashpadDateTime(report_dict['Creation time'])
          report_path = report_dict['Path'].strip()
          reports_list.append((report_time, report_path))
        except (ValueError, KeyError) as e:
          logging.warning('Crashpad report expected valid keys'
                          ' "Path" and "Creation time": %s', e)
        finally:
          report_dict = {}

      last_indentation = current_indentation

    # Include the last report.
    if report_dict:
      try:
        report_time = ParseCrashpadDateTime(report_dict['Creation time'])
        report_path = report_dict['Path'].strip()
        reports_list.append((report_time, report_path))
      except (ValueError, KeyError) as e:
        logging.warning('Crashpad report expected valid keys'
                          ' "Path" and "Creation time": %s', e)

    if reports_list:
      _, most_recent_report_path = max(reports_list)
      return most_recent_report_path

    return None

  def _GetMostRecentMinidump(self):
    # Crashpad dump layout will be the standard eventually, check it first.
    most_recent_dump = self._GetMostRecentCrashpadMinidump()

    # Typical breakpad format is simply dump files in a folder.
    if not most_recent_dump:
      dumps = glob.glob(os.path.join(self._tmp_minidump_dir, '*.dmp'))
      if dumps:
        most_recent_dump = heapq.nlargest(1, dumps, os.path.getmtime)[0]

    # As a sanity check, make sure the crash dump is recent.
    if (most_recent_dump and
        os.path.getmtime(most_recent_dump) < (time.time() - (5 * 60))):
      logging.warning('Crash dump is older than 5 minutes. May not be correct.')

    return most_recent_dump

  def _IsExecutableStripped(self):
    if self.browser.platform.GetOSName() == 'mac':
      try:
        symbols = subprocess.check_output(['/usr/bin/nm', self._executable])
      except subprocess.CalledProcessError as err:
        logging.warning('Error when checking whether executable is stripped: %s'
                        % err.output)
        # Just assume that binary is stripped to skip breakpad symbol generation
        # if this check failed.
        return True
      num_symbols = len(symbols.splitlines())
      # We assume that if there are more than 10 symbols the executable is not
      # stripped.
      return num_symbols < 10
    else:
      return False

  def _GetStackFromMinidump(self, minidump):
    os_name = self.browser.platform.GetOSName()
    if os_name == 'win':
      cdb = self._GetCdbPath()
      if not cdb:
        logging.warning('cdb.exe not found.')
        return None
      output = subprocess.check_output([cdb, '-y', self._browser_directory,
                                        '-c', '.ecxr;k30;q', '-z', minidump])
      # cdb output can start the stack with "ChildEBP", "Child-SP", and possibly
      # other things we haven't seen yet. If we can't find the start of the
      # stack, include output from the beginning.
      stack_start = 0
      stack_start_match = re.search("^Child(?:EBP|-SP)", output, re.MULTILINE)
      if stack_start_match:
        stack_start = stack_start_match.start()
      stack_end = output.find('quit:')
      return output[stack_start:stack_end]

    arch_name = self.browser.platform.GetArchName()
    stackwalk = binary_manager.FetchPath(
        'minidump_stackwalk', arch_name, os_name)
    if not stackwalk:
      logging.warning('minidump_stackwalk binary not found.')
      return None

    with open(minidump, 'rb') as infile:
      minidump += '.stripped'
      with open(minidump, 'wb') as outfile:
        outfile.write(''.join(infile.read().partition('MDMP')[1:]))

    symbols_path = os.path.join(self._tmp_minidump_dir, 'symbols')

    symbols = glob.glob(os.path.join(self._browser_directory, '*.breakpad*'))
    if symbols:
      for symbol in sorted(symbols, key=os.path.getmtime, reverse=True):
        if not os.path.isfile(symbol):
          continue
        with open(symbol, 'r') as f:
          fields = f.readline().split()
          if not fields:
            continue
          sha = fields[3]
          binary = ' '.join(fields[4:])
        symbol_path = os.path.join(symbols_path, binary, sha)
        if os.path.exists(symbol_path):
          continue
        os.makedirs(symbol_path)
        shutil.copyfile(symbol, os.path.join(symbol_path, binary + '.sym'))
    else:

      # On some platforms generating the symbol table can be very time
      # consuming, skip it if there's nothing to dump.
      if self._IsExecutableStripped():
        logging.info('%s appears to be stripped, skipping symbol dump.' % (
            self._executable))
        return

      logging.info('Dumping breakpad symbols.')
      generate_breakpad_symbols_command = binary_manager.FetchPath(
          'generate_breakpad_symbols', arch_name, os_name)
      if generate_breakpad_symbols_command is None:
        return

      for executable in GetSymbolBinaries(self._executable,
                                          self.browser.platform.GetOSName()):
        cmd = [
            sys.executable,
            generate_breakpad_symbols_command,
            '--binary=%s' % executable,
            '--symbols-dir=%s' % symbols_path,
            '--build-dir=%s' % self._browser_directory,
            ]

        try:
          subprocess.check_output(cmd, stderr=open(os.devnull, 'w'))
        except subprocess.CalledProcessError:
          logging.warning('Failed to execute "%s"' % ' '.join(cmd))
          return

    return subprocess.check_output([stackwalk, minidump, symbols_path],
                                   stderr=open(os.devnull, 'w'))

  def _UploadMinidumpToCloudStorage(self, minidump_path):
    """ Upload minidump_path to cloud storage and return the cloud storage url.
    """
    remote_path = ('minidump-%s-%i.dmp' %
                   (datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                    random.randint(0, 1000000)))
    try:
      return cloud_storage.Insert(cloud_storage.TELEMETRY_OUTPUT, remote_path,
                                  minidump_path)
    except cloud_storage.CloudStorageError as err:
      logging.error('Cloud storage error while trying to upload dump: %s' %
                    repr(err))
      return '<Missing link>'

  def GetStackTrace(self):
    most_recent_dump = self._GetMostRecentMinidump()
    if not most_recent_dump:
      return 'No crash dump found.'
    logging.info('Minidump found: %s' % most_recent_dump)
    stack = self._GetStackFromMinidump(most_recent_dump)
    if not stack:
      cloud_storage_link = self._UploadMinidumpToCloudStorage(most_recent_dump)
      return ('Failed to symbolize minidump. Raw stack is uploaded to cloud '
              'storage: %s.' % cloud_storage_link)
    return stack

  def __del__(self):
    self.Close()

  def _TryCooperativeShutdown(self):
    if self.browser.platform.IsCooperativeShutdownSupported():
      # Ideally there would be a portable, cooperative shutdown
      # mechanism for the browser. This seems difficult to do
      # correctly for all embedders of the content API. The only known
      # problem with unclean shutdown of the browser process is on
      # Windows, where suspended child processes frequently leak. For
      # now, just solve this particular problem. See Issue 424024.
      if self.browser.platform.CooperativelyShutdown(self._proc, "chrome"):
        try:
          util.WaitFor(lambda: not self.IsBrowserRunning(), timeout=5)
          logging.info('Successfully shut down browser cooperatively')
        except exceptions.TimeoutException as e:
          logging.warning('Failed to cooperatively shutdown. ' +
                          'Proceeding to terminate: ' + str(e))

  def Close(self):
    super(DesktopBrowserBackend, self).Close()

    if self.IsBrowserRunning():
      self._TryCooperativeShutdown()

    # Shutdown politely if the profile may be used again.
    if self._output_profile_path and self.IsBrowserRunning():
      self._proc.terminate()
      try:
        util.WaitFor(lambda: not self.IsBrowserRunning(), timeout=5)
        self._proc = None
      except exceptions.TimeoutException:
        logging.warning('Failed to gracefully shutdown. Proceeding to kill.')

    # Shutdown aggressively if the above failed or if the profile is temporary.
    if self.IsBrowserRunning():
      self._proc.kill()
    self._proc = None

    if self._crash_service:
      self._crash_service.kill()
      self._crash_service = None

    if self._output_profile_path:
      # If we need the output then double check that it exists.
      if not (self._tmp_profile_dir and os.path.exists(self._tmp_profile_dir)):
        raise Exception("No profile directory generated by Chrome: '%s'." %
            self._tmp_profile_dir)
    else:
      # If we don't need the profile after the run then cleanup.
      if self._tmp_profile_dir and os.path.exists(self._tmp_profile_dir):
        shutil.rmtree(self._tmp_profile_dir, ignore_errors=True)
        self._tmp_profile_dir = None

    if self._tmp_output_file:
      self._tmp_output_file.close()
      self._tmp_output_file = None
