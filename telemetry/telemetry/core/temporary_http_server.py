# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import socket
import subprocess
import sys
import urlparse

from telemetry.core import util

class TemporaryHTTPServer(object):
  def __init__(self, browser_backend, paths):
    self._server = None
    self._devnull = None
    self._forwarder = None

    for path in paths:
      assert os.path.exists(path), '%s does not exist.' % path
    self._paths = set(map(os.path.realpath, paths))

    common_prefix = os.path.commonprefix(self._paths)
    if os.path.isdir(common_prefix):
      self._base_dir = common_prefix
    else:
      self._base_dir = os.path.dirname(common_prefix)

    self._devnull = open(os.devnull, 'w')
    cmd = [sys.executable, '-m', 'memory_cache_http_server']
    cmd.extend(self._paths)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.abspath(os.path.dirname(__file__))
    self._server = subprocess.Popen(cmd, cwd=self._base_dir,
        env=env, stdout=subprocess.PIPE, stderr=self._devnull)

    port_re = re.compile(
        '.*(?P<protocol>HTTPS?) server started on (?P<host>.*):(?P<port>\d+)')
    while self._server.poll() == None:
      m = port_re.match(self._server.stdout.readline())
      if m:
        port = int(m.group('port'))
        break

    self._forwarder = browser_backend.CreateForwarder(
        util.PortPair(port, browser_backend.GetRemotePort(port)))

    def IsServerUp():
      return not socket.socket().connect_ex(('localhost', port))
    util.WaitFor(IsServerUp, 10)

  @property
  def paths(self):
    return self._paths

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def __del__(self):
    self.Close()

  def Close(self):
    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None
    if self._server:
      # TODO(tonyg): Should this block until it goes away?
      self._server.kill()
      self._server = None
    if self._devnull:
      self._devnull.close()
      self._devnull = None

  @property
  def url(self):
    return self._forwarder.url

  def UrlOf(self, path):
    relative_path = os.path.relpath(path, self._base_dir)
    # Preserve trailing slash or backslash.
    # It doesn't matter in a file path, but it does matter in a URL.
    if path.endswith(os.sep) or (os.altsep and path.endswith(os.altsep)):
      relative_path += '/'
    return urlparse.urljoin(self.url, relative_path.replace(os.sep, '/'))
