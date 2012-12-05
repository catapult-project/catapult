# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os as os
import subprocess as subprocess
import shutil
import tempfile

from telemetry import browser_backend
from telemetry import util

DEFAULT_PORT = 9273

class DesktopBrowserBackend(browser_backend.BrowserBackend):
  """The backend for controlling a locally-executed browser instance, on Linux,
  Mac or Windows.
  """
  def __init__(self, options, executable, is_content_shell):
    super(DesktopBrowserBackend, self).__init__(is_content_shell, options)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._proc = None
    self._devnull = None
    self._tmpdir = None

    self._executable = executable
    if not self._executable:
      raise Exception('Cannot create browser, no executable found!')

    self._port = DEFAULT_PORT
    args = [self._executable]
    args.extend(self.GetBrowserStartupArgs())
    if not options.show_stdout:
      self._devnull = open(os.devnull, 'w')
      self._proc = subprocess.Popen(
        args, stdout=self._devnull, stderr=self._devnull)
    else:
      self._devnull = None
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
    args.append('--window-size=1280,1024')
    args.append('--enable-benchmarking')
    if not self.options.dont_override_profile:
      self._tmpdir = tempfile.mkdtemp()
      args.append('--user-data-dir=%s' % self._tmpdir)
    return args

  def IsBrowserRunning(self):
    return self._proc.poll() == None

  def __del__(self):
    self.Close()

  def Close(self):
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

    if self._tmpdir and os.path.exists(self._tmpdir):
      shutil.rmtree(self._tmpdir, ignore_errors=True)
      self._tmpdir = None

    if self._devnull:
      self._devnull.close()
      self._devnull = None

  def CreateForwarder(self, *ports):
    return DoNothingForwarder(ports[0])

class DoNothingForwarder(object):
  def __init__(self, *port_pairs):
    self._host_port = port_pairs[0][0]

  @property
  def url(self):
    assert self._host_port
    return 'http://localhost:%i' % self._host_port

  def Close(self):
    self._host_port = None
