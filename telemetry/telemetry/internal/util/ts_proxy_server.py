# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Start and stop tsproxy."""

import logging
import os
import re
import subprocess
import sys
import time

try:
  import fcntl
except ImportError:
  fcntl = None

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.internal.util import ps_util

import py_utils
from py_utils import atexit_with_log


_TSPROXY_PATH = os.path.join(
    util.GetTelemetryThirdPartyDir(), 'tsproxy', 'tsproxy.py')


def ParseTsProxyPortFromOutput(output_line):
  port_re = re.compile(
      r'Started Socks5 proxy server on '
      r'(?P<host>[^:]*):'
      r'(?P<port>\d+)')
  m = port_re.match(output_line)
  if m:
    return int(m.group('port'))


class TsProxyServer(object):
  """Start and Stop Tsproxy.

  TsProxy provides basic latency, download and upload traffic shaping. This
  class provides a programming API to the tsproxy script in
  telemetry/third_party/tsproxy/tsproxy.py
  """

  def __init__(self, host_ip=None, http_port=None, https_port=None):
    """Initialize TsProxyServer.
    """
    self._proc = None
    self._port = None
    self._is_running = False
    self._host_ip = host_ip
    assert bool(http_port) == bool(https_port)
    self._http_port = http_port
    self._https_port = https_port
    self._non_blocking = False
    self._rtt = None
    self._inbkps = None
    self._outkbps = None

  @property
  def port(self):
    return self._port

  def StartServer(self, timeout=10):
    """Start TsProxy server and verify that it started.
    """
    cmd_line = [sys.executable, _TSPROXY_PATH]
    cmd_line.extend([
        '--port=0'])  # Use port 0 so tsproxy picks a random available port.
    if self._host_ip:
      cmd_line.append('--desthost=%s' % self._host_ip)
    if self._http_port:
      cmd_line.append(
          '--mapports=443:%s,*:%s' % (self._https_port, self._http_port))
    logging.info('Tsproxy commandline: %r' % cmd_line)
    self._proc = subprocess.Popen(
        cmd_line, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=1)
    self._non_blocking = False
    if fcntl:
      logging.info('fcntl is supported, try setting '
                   'non blocking I/O for the ts_proxy process')
      fd = self._proc.stdout.fileno()
      fl = fcntl.fcntl(fd, fcntl.F_GETFL)
      fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
      self._non_blocking = True

    atexit_with_log.Register(self.StopServer)
    try:
      py_utils.WaitFor(self._IsStarted, timeout)
      logging.info('TsProxy port: %s', self._port)
      self._is_running = True
    except py_utils.TimeoutException:
      # TODO(nedn): remove this debug log once crbug.com/766877 is resolved
      ps_util.ListAllSubprocesses()
      err = self.StopServer()
      if err:
        logging.error('Error stopping WPR server:\n%s', err)
      raise exceptions.Error(
          'Error starting tsproxy: timed out after %s seconds' % timeout)

  def _IsStarted(self):
    assert not self._is_running
    assert self._proc
    if self._proc.poll() is not None:
      return False
    self._proc.stdout.flush()
    output_line = self._ReadLineTsProxyStdout(timeout=5)
    logging.debug('TsProxy output: %s', output_line)
    self._port = ParseTsProxyPortFromOutput(output_line)
    return self._port != None

  def _ReadLineTsProxyStdout(self, timeout):
    def ReadlLine():
      try:
        return self._proc.stdout.readline().strip()
      except IOError:
        # Add a sleep to avoid trying to read self._proc.stdout too often.
        if self._non_blocking:
          time.sleep(0.5)
        return None
    return py_utils.WaitFor(ReadlLine, timeout)

  def _IssueCommand(self, command_string, timeout):
    logging.info('Issuing command to ts_proxy_server: %s', command_string)
    command_output = []
    self._proc.stdin.write('%s\n' % command_string)
    self._proc.stdin.flush()
    self._proc.stdout.flush()
    def CommandStatusIsRead():
      command_output.append(self._ReadLineTsProxyStdout(timeout))
      return command_output[-1] == 'OK' or command_output[-1] == 'ERROR'

    py_utils.WaitFor(CommandStatusIsRead, timeout)

    success = 'OK' in command_output
    logging.log(logging.DEBUG if success else logging.ERROR,
                'TsProxy output:\n%s', '\n'.join(command_output))
    if not success:
      raise exceptions.Error('Failed to execute command: %s', command_string)

  def UpdateOutboundPorts(self, http_port, https_port, timeout=5):
    assert http_port and https_port
    assert http_port != https_port
    assert isinstance(http_port, int) and isinstance(https_port, int)
    assert 1 <= http_port <= 65535
    assert 1 <= https_port <= 65535
    self._IssueCommand('set mapports 443:%i,*:%i' % (https_port, http_port),
                       timeout)

  def UpdateTrafficSettings(
      self, round_trip_latency_ms=None,
      download_bandwidth_kbps=None, upload_bandwidth_kbps=None, timeout=20):
    """Update traffic settings of the proxy server.

    Notes that this method only updates the specified parameter
    """
    # Memorize the traffic settings & only execute the command if the traffic
    # settings are different.
    if round_trip_latency_ms is not None and self._rtt != round_trip_latency_ms:
      self._IssueCommand('set rtt %s' % round_trip_latency_ms, timeout)
      self._rtt = round_trip_latency_ms

    if (download_bandwidth_kbps is not None and
        self._inbkps != download_bandwidth_kbps):
      self._IssueCommand('set inkbps %s' % download_bandwidth_kbps, timeout)
      self._inbkps = download_bandwidth_kbps

    if (upload_bandwidth_kbps is not None and
        self._outkbps != upload_bandwidth_kbps):
      self._IssueCommand('set outkbps %s' % upload_bandwidth_kbps, timeout)
      self._outkbps = upload_bandwidth_kbps

  def StopServer(self):
    """Stop TsProxy Server."""
    if not self._is_running:
      logging.debug('Attempting to stop TsProxy server that is not running.')
      return
    if self._proc:
      self._proc.terminate()
      self._proc.wait()
    err = self._proc.stderr.read()
    self._proc = None
    self._port = None
    self._is_running = False
    self._rtt = None
    self._inbkps = None
    self._outkbps = None
    return err

  def __enter__(self):
    """Add support for with-statement."""
    self.StartServer()
    return self

  def __exit__(self, unused_exc_type, unused_exc_val, unused_exc_tb):
    """Add support for with-statement."""
    self.StopServer()
