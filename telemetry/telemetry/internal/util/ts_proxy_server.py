# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Start and stop tsproxy."""

import logging
import os
import re
import subprocess
import sys

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.internal.util import atexit_with_log


_TSPROXY_PATH = os.path.join(
    util.GetTelemetryThirdPartyDir(), 'tsproxy', 'tsproxy.py')


def ParseTsProxyPortFromOutput(output_line):
  port_re = re.compile(
      r'Started Socks5 proxy server on '
      r'(?P<host>[^:]*):'
      r'(?P<port>\d+)')
  m = port_re.match(output_line.strip())
  if m:
    return int(m.group('port'))


class TsProxyServer(object):
  """Start and Stop Tsproxy.

  TsProxy provides basic latency, download and upload traffic shaping. This
  class provides a programming API to the tsproxy script in
  telemetry/third_party/tsproxy/tsproxy.py
  """

  def __init__(self, http_port, https_port):
    """Initialize TsProxyServer.
    """
    self._proc = None
    self._port = None
    self._http_port = http_port
    self._https_port = https_port

  @property
  def port(self):
    return self._port

  def StartServer(self, timeout=10):
    """Start TsProxy server and verify that it started.
    """
    cmd_line = [sys.executable, _TSPROXY_PATH]
    cmd_line.extend([
        '--port=0',  # Use port 0 so tsproxy picks a random available port.
        '--mapports=4a43:%s,*:%s' % (self._https_port, self._http_port)
        ])
    logging.info('Tsproxy commandline: %r' % cmd_line)
    self._proc = subprocess.Popen(
        cmd_line, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=1)
    atexit_with_log.Register(self.StopServer)
    try:
      util.WaitFor(self._IsStarted, timeout)
    except exceptions.TimeoutException:
      err = self.StopServer()
      raise RuntimeError(
          'Error starting tsproxy: %s' % err)

  def _IsStarted(self):
    assert self._proc
    if self._proc.poll() is not None:
      return False
    self._proc.stdout.flush()
    self._port = ParseTsProxyPortFromOutput(
          output_line=self._proc.stdout.readline())
    return self._port != None

  def StopServer(self):
    """Stop TsProxy Server."""
    if not self._proc:
      logging.warning('Attempting to stop TsProxy server that is not running.')
      return
    if self._proc:
      self._proc.terminate()
      self._proc.wait()
    err = self._proc.stderr.read()
    self._proc = None
    self._port = None
    return err

  def __enter__(self):
    """Add support for with-statement."""
    self.StartServer()
    return self

  def __exit__(self, unused_exc_type, unused_exc_val, unused_exc_tb):
    """Add support for with-statement."""
    self.StopServer()
