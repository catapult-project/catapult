# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Start and stop Web Page Replay.

Of the public module names, the following one is key:
  ReplayServer: a class to start/stop Web Page Replay.
"""

import logging
import os
import re
import signal
import subprocess
import sys
import time
import urllib


_CHROME_SRC_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))
REPLAY_DIR = os.path.join(
    _CHROME_SRC_DIR, 'third_party', 'webpagereplay')
LOG_PATH = os.path.join(
    _CHROME_SRC_DIR, 'webpagereplay_logs', 'logs.txt')


# Chrome options to make it work with Web Page Replay.
def GetChromeFlags(replay_host, http_port, https_port):
  assert replay_host and http_port and https_port, 'All arguments required'
  return [
      '--host-resolver-rules=MAP * %s,EXCLUDE localhost' % replay_host,
      '--testing-fixed-http-port=%s' % http_port,
      '--testing-fixed-https-port=%s' % https_port,
      '--ignore-certificate-errors',
      ]


# Signal masks on Linux are inherited from parent processes.  If anything
# invoking us accidentally masks SIGINT (e.g. by putting a process in the
# background from a shell script), sending a SIGINT to the child will fail
# to terminate it.  Running this signal handler before execing should fix that
# problem.
def ResetInterruptHandler():
  signal.signal(signal.SIGINT, signal.SIG_DFL)


class ReplayError(Exception):
  """Catch-all exception for the module."""
  pass


class ReplayNotFoundError(ReplayError):
  def __init__(self, label, path):
    super(ReplayNotFoundError, self).__init__()
    self.args = (label, path)

  def __str__(self):
    label, path = self.args
    return 'Path does not exist for %s: %s' % (label, path)


class ReplayNotStartedError(ReplayError):
  pass


class ReplayServer(object):
  """Start and Stop Web Page Replay.

  Web Page Replay is a proxy that can record and "replay" web pages with
  simulated network characteristics -- without having to edit the pages
  by hand. With WPR, tests can use "real" web content, and catch
  performance issues that may result from introducing network delays and
  bandwidth throttling.

  Example:
     with ReplayServer(archive_path):
       self.NavigateToURL(start_url)
       self.WaitUntil(...)

  Environment Variables (for development):
    WPR_ARCHIVE_PATH: path to alternate archive file (e.g. '/tmp/foo.wpr').
    WPR_RECORD: if set, puts Web Page Replay in record mode instead of replay.
    WPR_REPLAY_DIR: path to alternate Web Page Replay source.
  """

  def __init__(self, archive_path, replay_host, dns_port, http_port, https_port,
               replay_options=None, replay_dir=None,
               log_path=None):
    """Initialize ReplayServer.

    Args:
      archive_path: a path to a specific WPR archive (required).
      replay_host: the hostname to serve traffic.
      dns_port: an integer port on which to serve DNS traffic. May be zero
          to let the OS choose an available port. If None DNS forwarding is
          disabled.
      http_port: an integer port on which to serve HTTP traffic. May be zero
          to let the OS choose an available port.
      https_port: an integer port on which to serve HTTPS traffic. May be zero
          to let the OS choose an available port.
      replay_options: an iterable of options strings to forward to replay.py.
      replay_dir: directory that has replay.py and related modules.
      log_path: a path to a log file.
    """
    self.archive_path = os.environ.get('WPR_ARCHIVE_PATH', archive_path)
    self.replay_options = list(replay_options or ())
    self.replay_dir = os.environ.get('WPR_REPLAY_DIR', replay_dir or REPLAY_DIR)
    self.log_path = log_path or LOG_PATH
    self.dns_port = dns_port
    self.http_port = http_port
    self.https_port = https_port
    self._replay_host = replay_host

    if 'WPR_RECORD' in os.environ and '--record' not in self.replay_options:
      self.replay_options.append('--record')
    self.is_record_mode = '--record' in self.replay_options
    self._AddDefaultReplayOptions()

    self.replay_py = os.path.join(self.replay_dir, 'replay.py')

    if self.is_record_mode:
      self._CheckPath('archive directory', os.path.dirname(self.archive_path))
    elif not os.path.exists(self.archive_path):
      self._CheckPath('archive file', self.archive_path)
    self._CheckPath('replay script', self.replay_py)

    self.replay_process = None

  def _AddDefaultReplayOptions(self):
    """Set WPR command-line options. Can be overridden if needed."""
    self.replay_options = [
        '--host', str(self._replay_host),
        '--port', str(self.http_port),
        '--ssl_port', str(self.https_port),
        '--use_closest_match',
        '--no-dns_forwarding',
        '--log_level', 'warning'
        ] + self.replay_options
    if self.dns_port is not None:
      self.replay_options.extend(['--dns_port', str(self.dns_port)])

  def _CheckPath(self, label, path):
    if not os.path.exists(path):
      raise ReplayNotFoundError(label, path)

  def _OpenLogFile(self):
    log_dir = os.path.dirname(self.log_path)
    if not os.path.exists(log_dir):
      os.makedirs(log_dir)
    return open(self.log_path, 'w')

  def WaitForStart(self, timeout):
    """Checks to see if the server is up and running."""
    port_re = re.compile(
        '.*?(?P<protocol>[A-Z]+) server started on (?P<host>.*):(?P<port>\d+)')

    start_time = time.time()
    elapsed_time = 0
    while elapsed_time < timeout:
      if self.replay_process.poll() is not None:
        break  # The process has exited.

      # Read the ports from the WPR log.
      if not self.http_port or not self.https_port or not self.dns_port:
        with open(self.log_path) as f:
          for line in f.readlines():
            m = port_re.match(line.strip())
            if m:
              if not self.http_port and m.group('protocol') == 'HTTP':
                self.http_port = int(m.group('port'))
              elif not self.https_port and m.group('protocol') == 'HTTPS':
                self.https_port = int(m.group('port'))
              elif not self.dns_port and m.group('protocol') == 'DNS':
                self.dns_port = int(m.group('port'))

      # Try to connect to the WPR ports.
      if self.http_port and self.https_port:
        try:
          up_url = '%s://%s:%s/web-page-replay-generate-200'
          http_up_url = up_url % ('http', self._replay_host, self.http_port)
          https_up_url = up_url % ('https', self._replay_host, self.https_port)
          if (200 == urllib.urlopen(http_up_url, None, {}).getcode() and
              200 == urllib.urlopen(https_up_url, None, {}).getcode()):
            return True
        except IOError:
          pass

      poll_interval = min(max(elapsed_time / 10., .1), 5)
      time.sleep(poll_interval)
      elapsed_time = time.time() - start_time

    return False

  def StartServer(self):
    """Start Web Page Replay and verify that it started.

    Raises:
      ReplayNotStartedError: if Replay start-up fails.
    """
    cmd_line = [sys.executable, self.replay_py]
    cmd_line.extend(self.replay_options)
    cmd_line.append(self.archive_path)

    logging.debug('Starting Web-Page-Replay: %s', cmd_line)
    with self._OpenLogFile() as log_fh:
      kwargs = {'stdout': log_fh, 'stderr': subprocess.STDOUT}
      if sys.platform.startswith('linux') or sys.platform == 'darwin':
        kwargs['preexec_fn'] = ResetInterruptHandler
      self.replay_process = subprocess.Popen(cmd_line, **kwargs)

    if not self.WaitForStart(30):
      with open(self.log_path) as f:
        log = f.read()
      raise ReplayNotStartedError(
          'Web Page Replay failed to start. Log output:\n%s' % log)

  def StopServer(self):
    """Stop Web Page Replay."""
    if self.replay_process:
      logging.debug('Trying to stop Web-Page-Replay gracefully')
      try:
        urllib.urlopen('http://%s:%s/web-page-replay-command-exit' % (
            self._replay_host, self.http_port), None, {}).close()
      except IOError:
        # IOError is possible because the server might exit without response.
        pass

      start_time = time.time()
      while time.time() - start_time < 10:  # Timeout after 10 seconds.
        if self.replay_process.poll() is not None:
          break
        time.sleep(1)
      else:
        try:
          # Use a SIGINT so that it can do graceful cleanup.
          self.replay_process.send_signal(signal.SIGINT)
        except:  # pylint: disable=W0702
          # On Windows, we are left with no other option than terminate().
          if 'no-dns_forwarding' not in self.replay_options:
            logging.warning('DNS configuration might not be restored!')
          try:
            self.replay_process.terminate()
          except:  # pylint: disable=W0702
            pass
        self.replay_process.wait()

  def __enter__(self):
    """Add support for with-statement."""
    self.StartServer()
    return self

  def __exit__(self, unused_exc_type, unused_exc_val, unused_exc_tb):
    """Add support for with-statement."""
    self.StopServer()
