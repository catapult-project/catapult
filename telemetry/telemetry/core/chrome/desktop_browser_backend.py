# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import subprocess as subprocess
import shutil
import sys
import tempfile

from telemetry.core import util
from telemetry.core.chrome import browser_backend

class DesktopBrowserBackend(browser_backend.BrowserBackend):
  """The backend for controlling a locally-executed browser instance, on Linux,
  Mac or Windows.
  """
  def __init__(self, options, executable, is_content_shell,
               delete_profile_dir_after_run=True):
    super(DesktopBrowserBackend, self).__init__(
        is_content_shell=is_content_shell,
        supports_extensions=not is_content_shell,
        options=options)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._proc = None
    self._tmpdir = None
    self._tmp_output_file = None

    self._executable = executable
    if not self._executable:
      raise Exception('Cannot create browser, no executable found!')

    if len(options.extensions_to_load) > 0 and is_content_shell:
      raise browser_backend.ExtensionsNotSupportedException(
          'Content shell does not support extensions.')

    self._port = util.GetAvailableLocalPort()
    self._profile_dir = None
    self._supports_net_benchmarking = True
    self._delete_profile_dir_after_run = delete_profile_dir_after_run
    self._LaunchBrowser(options)

    # For old chrome versions, might have to relaunch to have the
    # correct net_benchmarking switch.
    if self._chrome_branch_number < 1418:
      self.Close()
      self._supports_net_benchmarking = False
      self._LaunchBrowser(options)

  def _LaunchBrowser(self, options):
    args = [self._executable]
    args.extend(self.GetBrowserStartupArgs())
    if not options.show_stdout:
      self._tmp_output_file = tempfile.NamedTemporaryFile('w', 0)
      self._proc = subprocess.Popen(
          args, stdout=self._tmp_output_file, stderr=subprocess.STDOUT)
    else:
      self._proc = subprocess.Popen(args)

    try:
      self._WaitForBrowserToComeUp()
      self._PostBrowserStartupInitialization()
    except:
      self.Close()
      raise

  def GetBrowserStartupArgs(self):
    args = super(DesktopBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--remote-debugging-port=%i' % self._port)
    if not self.is_content_shell:
      args.append('--window-size=1280,1024')
      if self._supports_net_benchmarking:
        args.append('--enable-net-benchmarking')
      else:
        args.append('--enable-benchmarking')
      if not self.options.dont_override_profile:
        self._tmpdir = tempfile.mkdtemp()
        profile_dir = self._profile_dir or self.options.profile_dir
        if profile_dir:
          if self.is_content_shell:
            logging.critical('Profiles cannot be used with content shell')
            sys.exit(1)
          shutil.rmtree(self._tmpdir)
          shutil.copytree(profile_dir, self._tmpdir)
        args.append('--user-data-dir=%s' % self._tmpdir)
    return args

  def SetProfileDirectory(self, profile_dir):
    # Make sure _profile_dir hasn't already been set.
    assert self._profile_dir is None

    if self.is_content_shell:
      logging.critical('Profile creation cannot be used with content shell')
      sys.exit(1)

    self._profile_dir = profile_dir

  @property
  def pid(self):
    if self._proc:
      return self._proc.pid
    return None


  @property
  def profile_directory(self):
    return self._tmpdir

  def IsBrowserRunning(self):
    return self._proc.poll() == None

  def GetStandardOutput(self):
    assert self._tmp_output_file, "Can't get standard output with show_stdout"
    self._tmp_output_file.flush()
    try:
      with open(self._tmp_output_file.name) as f:
        return f.read()
    except IOError:
      return ''

  def __del__(self):
    self.Close()

  def Close(self):
    super(DesktopBrowserBackend, self).Close()

    if self._proc:

      def IsClosed():
        if not self._proc:
          return True
        return self._proc.poll() != None

      # Try to politely shutdown, first.
      self._proc.terminate()
      try:
        util.WaitFor(IsClosed, timeout=1)
        self._proc = None
      except util.TimeoutException:
        pass

      # Kill it.
      if not IsClosed():
        self._proc.kill()
        try:
          util.WaitFor(IsClosed, timeout=5)
          self._proc = None
        except util.TimeoutException:
          self._proc = None
          raise Exception('Could not shutdown the browser.')

    if self._delete_profile_dir_after_run and \
        self._tmpdir and os.path.exists(self._tmpdir):
      shutil.rmtree(self._tmpdir, ignore_errors=True)
      self._tmpdir = None

    if self._tmp_output_file:
      self._tmp_output_file.close()
      self._tmp_output_file = None

  def CreateForwarder(self, *port_pairs):
    return browser_backend.DoNothingForwarder(*port_pairs)
