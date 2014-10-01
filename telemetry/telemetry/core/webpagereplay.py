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
import urllib

from telemetry.core import util

_CHROME_SRC_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir))
REPLAY_DIR = os.path.join(
    _CHROME_SRC_DIR, 'third_party', 'webpagereplay')
LOG_PATH = os.path.join(
    _CHROME_SRC_DIR, 'webpagereplay_logs', 'logs.txt')


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

  def __init__(self, archive_path, replay_host, http_port, https_port, dns_port,
               replay_options=None, replay_dir=None,
               log_path=None):
    """Initialize ReplayServer.

    Args:
      archive_path: a path to a specific WPR archive (required).
      replay_host: the hostname to serve traffic.
      http_port: an integer port on which to serve HTTP traffic. May be zero
          to let the OS choose an available port.
      https_port: an integer port on which to serve HTTPS traffic. May be zero
          to let the OS choose an available port.
      dns_port: an integer port on which to serve DNS traffic. May be zero
          to let the OS choose an available port. If None DNS forwarding is
          disabled.
      replay_options: an iterable of options strings to forward to replay.py.
      replay_dir: directory that has replay.py and related modules.
      log_path: a path to a log file.
    """
    self.archive_path = os.environ.get('WPR_ARCHIVE_PATH', archive_path)
    self.replay_options = list(replay_options or ())
    self.replay_dir = os.environ.get('WPR_REPLAY_DIR', replay_dir or REPLAY_DIR)
    self.log_path = log_path or LOG_PATH
    self._replay_host = replay_host
    self._use_dns_server = dns_port is not None
    self._started_ports = {}  # a dict such as {'http': 80, 'https': 443}

    if 'WPR_RECORD' in os.environ and '--record' not in self.replay_options:
      self.replay_options.append('--record')
    self.is_record_mode = '--record' in self.replay_options
    self._AddDefaultReplayOptions(http_port, https_port, dns_port)

    self.replay_py = os.path.join(self.replay_dir, 'replay.py')

    if self.is_record_mode:
      self._CheckPath('archive directory', os.path.dirname(self.archive_path))
    elif not os.path.exists(self.archive_path):
      self._CheckPath('archive file', self.archive_path)
    self._CheckPath('replay script', self.replay_py)

    self.replay_process = None

  def _AddDefaultReplayOptions(self, http_port, https_port, dns_port):
    """Set WPR command-line options. Can be overridden if needed."""
    self.replay_options = [
        '--host=%s' % self._replay_host,
        '--port=%s' % http_port,
        '--ssl_port=%s' % https_port,
        '--use_closest_match',
        '--no-dns_forwarding',
        '--log_level=warning'
        ] + self.replay_options
    if self._use_dns_server:
      # Note that if --host is not '127.0.0.1', Replay will override the local
      # DNS nameserver settings to point to the replay-started DNS server.
      self.replay_options.append('--dns_port=%s' % dns_port)

  def _CheckPath(self, label, path):
    if not os.path.exists(path):
      raise ReplayNotFoundError(label, path)

  def _OpenLogFile(self):
    """Opens the log file for writing."""
    log_dir = os.path.dirname(self.log_path)
    if not os.path.exists(log_dir):
      os.makedirs(log_dir)
    return open(self.log_path, 'w')

  def _LogLines(self):
    """Yields the log lines."""
    if not os.path.isfile(self.log_path):
      return
    with open(self.log_path) as f:
      for line in f:
        yield line

  def _IsStarted(self):
    """Returns true if the server is up and running."""
    if self.replay_process.poll() is not None:
      # The process terminated.
      return False

    def HasIncompleteStartedPorts():
      return ('http' not in self._started_ports or
              'https' not in self._started_ports or
              (self._use_dns_server and 'dns' not in self._started_ports))
    if HasIncompleteStartedPorts():
      self._started_ports = self._ParseLogFilePorts(self._LogLines())
    if HasIncompleteStartedPorts():
      return False
    try:
      # HTTPS may require SNI (which urllib does not speak), so only check
      # that HTTP responds.
      return 200 == self._UrlOpen('web-page-replay-generate-200').getcode()
    except IOError:
      return False

  @staticmethod
  def _ParseLogFilePorts(log_lines):
    """Returns the ports on which replay listens as reported in its log file.

    Only matches HTTP, HTTPS, and DNS. One call may return only some
    of the ports depending on what has been written to the log file.

    Example log lines:
        2014-09-03 17:04:27,978 WARNING HTTP server started on 127.0.0.1:51673
        2014-09-03 17:04:27,978 WARNING HTTPS server started on 127.0.0.1:35270

    Returns:
      a dict with ports available in log_lines. For example,
         {}  # no ports found
         {'http': 1234, 'https': 2345, 'dns': 3456}
    """
    ports = {}
    port_re = re.compile(
        r'.*?(?P<protocol>HTTP|HTTPS|DNS)'
        r' server started on '
        r'(?P<host>[^:]*):'
        r'(?P<port>\d+)')
    for line in log_lines:
      m = port_re.match(line.strip())
      if m:
        protocol = m.group('protocol').lower()
        ports[protocol] = int(m.group('port'))
    return ports

  def StartServer(self):
    """Start Web Page Replay and verify that it started.

    Returns:
      (HTTP_PORT, HTTPS_PORT, DNS_PORT)  # DNS_PORT is None if unused.
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

    try:
      util.WaitFor(self._IsStarted, 30)
      return (
          self._started_ports['http'],
          self._started_ports['https'],
          self._started_ports.get('dns'),  # None if unused
          )
    except util.TimeoutException:
      raise ReplayNotStartedError(
          'Web Page Replay failed to start. Log output:\n%s' %
          ''.join(self._LogLines()))

  def StopServer(self):
    """Stop Web Page Replay."""
    if not self.replay_process:
      return

    logging.debug('Trying to stop Web-Page-Replay gracefully')
    try:
      if self._started_ports:
        self._UrlOpen('web-page-replay-command-exit').close()
    except IOError:
      # IOError is possible because the server might exit without response.
      pass

    try:
      util.WaitFor(lambda: self.replay_process.poll() is not None, 10)
    except util.TimeoutException:
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

  def _UrlOpen(self, url_path, protocol='http'):
    """Open a Replay URL.

    For matching requests in the archive, Replay relies on the "Host:" header.
    For Replay command URLs, the "Host:" header is not needed.

    Args:
      url_path: WPR server request path.
      protocol: 'http' or 'https'
    Returns:
      a file-like object from urllib.urlopen
    """
    url = '%s://%s:%s/%s' % (
        protocol, self._replay_host, self._started_ports[protocol], url_path)
    return urllib.urlopen(url, proxies={})
