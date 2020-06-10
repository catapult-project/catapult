# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Start and stop Web Page Replay."""

import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import urllib

import py_utils
from py_utils import atexit_with_log
from py_utils import binary_manager


_WPR_DIR = os.path.abspath(os.path.join(
    py_utils.GetCatapultDir(), 'web_page_replay_go'))

TELEMETRY_PROJECT_CONFIG = os.path.join(
    py_utils.GetCatapultDir(), 'telemetry', 'telemetry',
    'binary_dependencies.json')

CHROME_BINARY_CONFIG = os.path.join(
    py_utils.GetCatapultDir(), 'common', 'py_utils', 'py_utils',
    'chrome_binaries.json')

RECORD = '--record'
INJECT_SCRIPTS = '--inject_scripts='

class ReplayError(Exception):
  """Catch-all exception for the module."""
  pass


class ReplayNotFoundError(ReplayError):
  def __init__(self, label, path):
    """
    Create a ReplayNotFoundError instance.

    Args:

      label: A string of label of this error.
      path: A string of the path in this error.

    """
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

  This class could be used as a context manager.

  Example:
     with ReplayServer(archive_path):
       self.NavigateToURL(start_url)
       self.WaitUntil(...)
  """

  _go_binary_path = None

  def __init__(self, archive_path, replay_host, http_port, https_port,
               replay_options, binary_downloader=None):
    """Initialize ReplayServer.

    Args:
      archive_path: a path to a specific WPR archive.
      replay_host: the hostname to serve traffic.
      http_port: an integer port on which to serve HTTP traffic. May be zero
          to let the OS choose an available port.
      https_port: an integer port on which to serve HTTPS traffic. May be zero
          to let the OS choose an available port.
      replay_options: an iterable of options strings to forward to replay.py.
      binary_downloader: a function to be used to fetch binary. May be None to
          use py_utils.binary_manager.FetchPath as default downloader.
    """
    self.archive_path = archive_path
    self._replay_host = replay_host
    self._started_ports = {}  # a dict such as {'http': 80, 'https': 443}

    # A temporary path for storing stdout & stderr of the webpagereplay
    # subprocess.
    self._temp_log_file_path = None

    # Assign the downloader func and binary_manager
    downloader = None
    if binary_downloader:
      downloader = binary_downloader
    else:
      configs = [CHROME_BINARY_CONFIG, TELEMETRY_PROJECT_CONFIG]
      downloader = binary_manager.BinaryManager(configs).FetchPath

    self._cmd_line = self._GetCommandLine(
        self._GetGoBinaryPath(downloader=downloader), http_port, https_port,
        replay_options, archive_path)

    if RECORD in replay_options or 'record' in replay_options:
      self._AssertPathExists('archive directory',
                             os.path.dirname(self.archive_path))
    elif not os.path.exists(self.archive_path):
      self._AssertPathExists('archive file', self.archive_path)

    self.replay_process = None

  @classmethod
  def _GetGoBinaryPath(cls, downloader):
    if not cls._go_binary_path:
      cls._go_binary_path = downloader(
          'wpr_go', py_utils.GetHostOsName(), py_utils.GetHostArchName())
    return cls._go_binary_path

  @classmethod
  def SetGoBinaryPath(cls, go_binary_path):
    """Overrides the _go_binary_path.

    This allows the server to use WPRGO files retrieved from somewhere
    other than GCS, such as CIPD."""
    cls._go_binary_path = go_binary_path

  @property
  def http_port(self):
    return self._started_ports['http']

  @property
  def https_port(self):
    return self._started_ports['https']

  @staticmethod
  def _GetCommandLine(go_binary_path, http_port, https_port,
                      options, archive_path):
    """Set WPR command-line arguments. Can be overridden if needed.

    Keyword arguments:

    * go_binary_path: A string of the path to the wpr.go binary.
    * http_port: A decimal of the port that handles http requests.
    * https_port: A decimal of the port that handles https requests.
    * options: A list of options, such as '--record',
        '--inject_scripts', etc.
    * archive_path: A string of the path to the archive file.

    """
    bad_options = []
    for option in options:
      if option not in [RECORD, INJECT_SCRIPTS]:
        bad_options.append(option)
    if len(bad_options) > 0:
      raise ValueError("Invalid replay options %s" % bad_options)

    cmd_line = [go_binary_path]
    if RECORD in options:
      cmd_line.append('record')
    else:
      cmd_line.append('replay')
    key_file = os.path.join(_WPR_DIR, 'wpr_key.pem')
    cert_file = os.path.join(_WPR_DIR, 'wpr_cert.pem')
    inject_script = os.path.join(_WPR_DIR, 'deterministic.js')
    cmd_line.extend([
        '--http_port=%s' % http_port,
        '--https_port=%s' % https_port,
        '--https_key_file=%s' % key_file,
        '--https_cert_file=%s' % cert_file])
    if INJECT_SCRIPTS in options:
      cmd_line.append(INJECT_SCRIPTS)
    else:
      cmd_line.append('--inject_scripts=%s' % inject_script)
    cmd_line.append(archive_path)
    return cmd_line

  def _AssertPathExists(self, label, path):
    if not os.path.exists(path):
      raise ReplayNotFoundError(label, path)

  def _OpenLogFile(self):
    """Opens the log file for writing."""
    log_dir = os.path.dirname(self._temp_log_file_path)
    if not os.path.isdir(log_dir):
      os.makedirs(log_dir)
    return open(self._temp_log_file_path, 'w')

  def _LogLines(self):
    """Yields any log lines that have been writtent to disk."""
    if (not self._temp_log_file_path or
        not os.path.isfile(self._temp_log_file_path)):
      yield '(N/A)'
      return
    with open(self._temp_log_file_path) as f:
      for line in f:
        yield line

  def _IsStarted(self):
    """Returns true if the server is up and running."""
    if not self._IsReplayProcessStarted():
      return False

    def HasIncompleteStartedPorts():
      return ('http' not in self._started_ports or
              'https' not in self._started_ports)

    if HasIncompleteStartedPorts():
      self._started_ports = self._ParseLogFilePorts(self._LogLines())
    if HasIncompleteStartedPorts():
      return False

    try:
      # HTTPS may require SNI (which urllib does not speak), so only check
      # that HTTP responds.
      return self._UrlOpen('web-page-replay-generate-200').getcode() == 200
    except IOError:
      return False

  @staticmethod
  def _ParseLogFilePorts(log_lines):
    """Returns the ports on which replay listens as reported in its log file.

    Only matches HTTP, HTTPS, and DNS. One call may return only some
    of the ports depending on what has been written to the log file.

    Example log lines:
      2014-09-03 17:04:27,978 Starting server on http://:51673
      2014-09-03 17:04:27,978 Starting server on https://:35270

    Returns:
      a dict with ports available in log_lines. For example,
         {}  # no ports found
         {'http': 1234, 'https': 2345, 'dns': 3456}
    """
    ports = {}
    port_re = re.compile(
        r'.*Starting server on '
        r'(?P<protocol>http|https)://'
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
      A dictionary mapping the keys 'http', 'https', and (if used) 'dns'
      to the respective ports of the replay server.
    Raises:
      ReplayNotStartedError: if Replay start-up fails.
    """
    is_posix = sys.platform.startswith('linux') or sys.platform == 'darwin'
    logging.info('Starting Web-Page-Replay: %s', self._cmd_line)
    self._CreateTempLogFilePath()
    with self._OpenLogFile() as log_fh:
      self.replay_process = subprocess.Popen(
          self._cmd_line, stdout=log_fh, stderr=subprocess.STDOUT,
          preexec_fn=(_ResetInterruptHandler if is_posix else None))
    try:
      # TODO(crbug.com/805418): consider changing this to wait with I/O timeout.
      # The 120s timeout is based on past failures (e.g: crbug.com/812639).
      py_utils.WaitFor(self._IsStarted, timeout=120)
      logging.info('WPR ports: %s', self._started_ports)
      atexit_with_log.Register(self.StopServer)
      return dict(self._started_ports)
    except Exception:
      self.StopServer(logging.ERROR)
      raise ReplayNotStartedError('Web Page Replay failed to start.')

  def _IsReplayProcessStarted(self):
    if not self.replay_process:
      return False
    return self.replay_process and self.replay_process.poll() is None

  def StopServer(self, log_level=logging.DEBUG):
    """Stop Web Page Replay.

    This also attempts to return stdout/stderr logs of wpr process if there is
    any. If there is none, '(N/A)' string is returned (see _LogLines()
    implementation).
    """
    if self._IsReplayProcessStarted():
      self._StopReplayProcess()
    self._CleanUpTempLogFilePath(log_level)
    self._started_ports = {}

  def _StopReplayProcess(self):
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
      py_utils.WaitFor(lambda: self.replay_process.poll() is not None, 10)
    except py_utils.TimeoutException:
      try:
        # Use a SIGINT so that it can do graceful cleanup.
        self.replay_process.send_signal(signal.SIGINT)
      except Exception:  # pylint: disable=broad-except
        # On Windows, we are left with no other option than terminate().
        is_primary_nameserver_changed_by_replay = (
            self._replay_host == '127.0.0.1')
        if is_primary_nameserver_changed_by_replay:
          # Replay changes the DNS nameserver configuration so that DNS
          # requests are resolved by replay's own DNS server. It resolves
          # all DNS requests to it own IP address to it can server the
          # HTTP and HTTPS requests.
          # If the replay host is not '127.0.0.1', then replay skips the
          # nameserver change because it assumes a different mechanism
          # will be used to route DNS requests to replay's DNS server.
          logging.warning(
              'Unable to stop Web-Page-Replay gracefully.\n'
              'Replay changed the DNS nameserver configuration to make replay '
              'the primary nameserver. That might not be restored!')
        self.replay_process.terminate()
      self.replay_process.communicate()
    finally:
      self.replay_process = None

  def _CreateTempLogFilePath(self):
    assert self._temp_log_file_path is None
    handle, self._temp_log_file_path = tempfile.mkstemp()
    os.close(handle)

  def _CleanUpTempLogFilePath(self, log_level):
    if not self._temp_log_file_path:
      return ''
    if logging.getLogger('').isEnabledFor(log_level):
      with open(self._temp_log_file_path, 'r') as f:
        wpr_log_output = f.read()
      logging.log(log_level, '\n'.join([
          '************************** WPR LOG *****************************',
          wpr_log_output,
          '************************** END OF WPR LOG **********************']))
    os.remove(self._temp_log_file_path)
    self._temp_log_file_path = None

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

def _ResetInterruptHandler():
  """Reset the interrupt handler back to the default.

  The replay process is stopped gracefully by making an HTTP request
  ('web-page-replay-command-exit'). The graceful exit is important for
  restoring the DNS configuration. If the HTTP request fails, the fallback
  is to send SIGINT to the process.

  On posix system, running this function before starting replay fixes a
  bug that shows up when Telemetry is run as a background command from a
  script. https://crbug.com/254572.

  Background: Signal masks on Linux are inherited from parent
  processes. If anything invoking us accidentally masks SIGINT
  (e.g. by putting a process in the background from a shell script),
  sending a SIGINT to the child will fail to terminate it.
  """
  signal.signal(signal.SIGINT, signal.SIG_DFL)
