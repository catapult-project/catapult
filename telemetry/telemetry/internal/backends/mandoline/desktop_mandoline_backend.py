# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import subprocess
import sys
import tempfile

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.internal.backends.mandoline import mandoline_browser_backend


class DesktopMandolineBackend(
    mandoline_browser_backend.MandolineBrowserBackend):
  """The backend for controlling a locally-executed browser instance, on Linux
  or Windows.
  """
  # It is OK to have abstract methods. pylint: disable=W0223

  def __init__(self, desktop_platform_backend, browser_options, executable,
               browser_directory):
    super(DesktopMandolineBackend, self).__init__(
        desktop_platform_backend,
        browser_options=browser_options)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._proc = None
    self._tmp_output_file = None

    self._tmp_profile_dir = None
    if not self.browser_options.profile_dir:
      self._tmp_profile_dir = tempfile.mkdtemp()
    logging.info("Using profile directory:'%s'." % self.profile_directory)

    self._executable = executable
    if not self._executable:
      raise Exception('Cannot create browser, no executable found!')

    self._browser_directory = browser_directory

  def HasBrowserFinishedLaunching(self):
    # In addition to the functional check performed by the base class, quickly
    # check if the browser process is still alive.
    if not self.IsBrowserRunning():
      raise exceptions.ProcessGoneException(
          "Return code: %d" % self._proc.returncode)
    return super(DesktopMandolineBackend, self).HasBrowserFinishedLaunching()

  def GetBrowserStartupArgs(self):
    args = super(DesktopMandolineBackend, self).GetBrowserStartupArgs()
    self._port = util.GetUnreservedAvailableLocalPort()
    logging.info('Requested remote debugging port: %d' % self._port)
    args.append('--remote-debugging-port=%i' % self._port)
    args.append('--user-data-dir=%s' % self.profile_directory)
    return args

  def Start(self):
    assert not self._proc, 'Must call Close() before Start()'

    args = [self._executable]
    args.extend(self.GetBrowserStartupArgs())
    if self.browser_options.startup_url:
      args.append(self.browser_options.startup_url)
    env = os.environ.copy()
    logging.debug('Starting Mandoline %s', args)

    if self._tmp_output_file:
      # Close the previous temp output file, if it exists. Please note that
      # Close() doesn't do this because GetStandardOutput() needs to access this
      # file and it may be called after Close().
      self._tmp_output_file.close()
      self._tmp_output_file = None

    if not self.browser_options.show_stdout:
      self._tmp_output_file = tempfile.NamedTemporaryFile()

      self._proc = subprocess.Popen(
          args, stdout=self._tmp_output_file, stderr=subprocess.STDOUT, env=env)
    else:
      self._proc = subprocess.Popen(args, env=env)

    try:
      self._WaitForBrowserToComeUp()
      self._InitDevtoolsClientBackend()
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
    return self.browser_options.profile_dir or self._tmp_profile_dir

  def IsBrowserRunning(self):
    return self._proc and self._proc.poll() == None

  def GetStandardOutput(self):
    if not self._tmp_output_file:
      if self.browser_options.show_stdout:
        # This can happen in the case that loading the mandoline binary fails.
        # We print rather than using logging here, because that makes a
        # recursive call to this function.
        print >> sys.stderr, "Can't get standard output with --show-stdout"
      return ''
    try:
      self._tmp_output_file.flush()
      self._tmp_output_file.seek(0)
      return self._tmp_output_file.read()
    except IOError:
      return ''

  def GetStackTrace(self):
    return ('Retrieving stack trace from the browser is not yet supported. '
            'Returning browser stdout:\n' + self.GetStandardOutput())

  def __del__(self):
    self.Close()

  def _TryCooperativeShutdown(self):
    if self.browser.platform.IsCooperativeShutdownSupported():
      if self.browser.platform.CooperativelyShutdown(self._proc, "mandoline"):
        try:
          util.WaitFor(lambda: not self.IsBrowserRunning(), timeout=5)
          logging.info('Successfully shut down browser cooperatively')
        except exceptions.TimeoutException as e:
          logging.warning('Failed to cooperatively shutdown. ' +
                          'Proceeding to terminate: ' + str(e))

  def Close(self):
    super(DesktopMandolineBackend, self).Close()

    if self.IsBrowserRunning():
      self._TryCooperativeShutdown()

    if self.IsBrowserRunning():
      self._proc.kill()
    self._proc = None

    if self._tmp_profile_dir and os.path.exists(self._tmp_profile_dir):
      shutil.rmtree(self._tmp_profile_dir, ignore_errors=True)
      self._tmp_profile_dir = None
