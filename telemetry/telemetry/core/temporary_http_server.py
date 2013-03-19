# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import socket
import subprocess
import sys
import urlparse

from telemetry.core import util

class TemporaryHTTPServer(object):
  def __init__(self, browser_backend, path):
    self._server = None
    self._devnull = None
    self._path = path
    self._forwarder = None

    self._host_port = util.GetAvailableLocalPort()

    assert os.path.exists(path), path
    assert os.path.isdir(path), path

    self._devnull = open(os.devnull, 'w')
    self._WarmDiskCache()
    self._server = subprocess.Popen(
        [sys.executable, '-m', 'SimpleHTTPServer', str(self._host_port)],
        cwd=self._path,
        stdout=self._devnull, stderr=self._devnull)

    self._forwarder = browser_backend.CreateForwarder(
        util.PortPair(self._host_port,
                      browser_backend.GetRemotePort(self._host_port)))

    def IsServerUp():
      return not socket.socket().connect_ex(('localhost', self._host_port))
    util.WaitFor(IsServerUp, 5)

  @property
  def path(self):
    return self._path

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def __del__(self):
    self.Close()

  def _WarmDiskCache(self):
    """Warm the disk cache for all files in self._path. This decreases the
    likelyhood of disk paging at serving time.
    """
    for root, _, files in os.walk(self._path):
      for f in files:
        file_path = os.path.join(root, f)
        if not os.path.exists(file_path):  # Allow for '.#' files
          continue
        with open(file_path, 'r') as fd:
          self._devnull.write(fd.read())

  def Close(self):
    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None
    if self._server:
      self._server.kill()
      self._server = None
    if self._devnull:
      self._devnull.close()
      self._devnull = None

  @property
  def url(self):
    return self._forwarder.url

  def UrlOf(self, path):
    return urlparse.urljoin(self.url, path)
