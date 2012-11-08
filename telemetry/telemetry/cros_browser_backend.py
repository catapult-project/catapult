# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import socket
import subprocess
import time

from telemetry import browser_backend
from telemetry import cros_interface

class CrOSBrowserBackend(browser_backend.BrowserBackend):
  """The backend for controlling a browser instance running on CrOS.
  """
  def __init__(self, browser_type, options, is_content_shell, cri):
    super(CrOSBrowserBackend, self).__init__(is_content_shell, options)
    # Initialize fields so that an explosion during init doesn't break in Close.
    self._options = options
    assert not is_content_shell
    self._cri = cri
    self._browser_type = browser_type

    tmp = socket.socket()
    tmp.bind(('', 0))
    self._port = tmp.getsockname()[1]
    tmp.close()

    self._remote_debugging_port = self._cri.GetRemotePort()
    self._tmpdir = None

    self._X = None
    self._proc = None

    # TODO(nduca): Stop ui if running.
    if self._cri.IsServiceRunning('ui'):
      # Note, if this hangs, its probably because they were using wifi AND they
      # had a user-specific wifi password, which when you stop ui kills the wifi
      # connection.
      logging.debug('stopping ui')
      self._cri.GetCmdOutput(['stop', 'ui'])

    # Set up user data dir.
    if not is_content_shell:
      logging.info('Preparing user data dir')
      self._tmpdir = '/tmp/telemetry'
      if options.dont_override_profile:
        # TODO(nduca): Implement support for this.
        logging.critical('Feature not (yet) implemented.')

      # Ensure a clean user_data_dir.
      self._cri.RmRF(self._tmpdir)

    # Set startup args.
    args = ['/opt/google/chrome/chrome']
    args.extend(self.GetBrowserStartupArgs())

    # Final bits of command line prep.
    def EscapeIfNeeded(arg):
      return arg.replace(' ', '" "')
    args = [EscapeIfNeeded(arg) for arg in args]
    prevent_output = not options.show_stdout

    # Stop old X.
    logging.info('Stoppping old X')
    self._cri.KillAllMatching(
      lambda name: name.startswith('/usr/bin/X '))

    # Start X.
    logging.info('Starting new X')
    X_args = ['/usr/bin/X',
              '-noreset',
              '-nolisten',
              'tcp',
              'vt01',
              '-auth',
              '/var/run/chromelogin.auth']
    self._X = cros_interface.DeviceSideProcess(
      self._cri, X_args, prevent_output=prevent_output)

    # Stop old chrome.
    logging.info('Killing old chrome')
    self._cri.KillAllMatching(
      lambda name: name.startswith('/opt/google/chrome/chrome '))

    # Start chrome via a bootstrap.
    logging.info('Starting chrome')
    self._proc = cros_interface.DeviceSideProcess(
      self._cri,
      args,
      prevent_output=prevent_output,
      extra_ssh_args=['-L%i:localhost:%i' % (
          self._port, self._remote_debugging_port)],
      leave_ssh_alive=True,
      env={'DISPLAY': ':0',
           'USER': 'chronos'},
      login_shell=True)

    # You're done.
    try:
      self._WaitForBrowserToComeUp()
    except:
      import traceback
      traceback.print_exc()
      self.Close()
      raise

  def GetBrowserStartupArgs(self):
    args = super(CrOSBrowserBackend, self).GetBrowserStartupArgs()

    args.extend([
            '--allow-webui-compositing',
            '--aura-host-window-use-fullscreen',
            '--enable-smooth-scrolling',
            '--enable-threaded-compositing',
            '--enable-per-tile-painting',
            '--enable-gpu-sandboxing',
            '--enable-accelerated-layers',
            '--force-compositing-mode',
            '--remote-debugging-port=%i' % self._remote_debugging_port,
            '--start-maximized'])
    if not self.is_content_shell:
      args.append('--user-data-dir=%s' % self._tmpdir)

    return args

  def __del__(self):
    self.Close()

  def Close(self):
    if self._proc:
      self._proc.Close()
      self._proc = None

    if self._X:
      self._X.Close()
      self._X = None

    if self._tmpdir:
      self._cri.RmRF(self._tmpdir)
      self._tmpdir = None

    self._cri = None

  def IsBrowserRunning(self):
    if not self._proc:
      return False
    return self._proc.IsAlive()

  def CreateForwarder(self, *ports):
    assert self._cri
    return SSHReverseForwarder(self._cri, *ports)


class SSHReverseForwarder(object):
  def __init__(self, cri, *ports):
    self._proc = None
    self._host_port = ports[0]

    self._proc = subprocess.Popen(
      cri.FormSSHCommandLine(['sleep', '99999999999'],
                             ['-R%i:localhost:%i' %
                              (port, port) for port in ports]),
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      stdin=subprocess.PIPE,
      shell=False)

    # TODO(nduca): How do we wait for the server to come up in a
    # robust way?
    time.sleep(1.5)

  @property
  def url(self):
    assert self._proc
    return 'http://localhost:%i' % self._host_port

  def Close(self):
    if self._proc:
      self._proc.kill()
      self._proc = None
