# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import BaseHTTPServer
import SimpleHTTPServer

from telemetry.core import local_server
from telemetry.unittest import tab_test_case

class SimpleLocalServerBackendRequestHandler(
    SimpleHTTPServer.SimpleHTTPRequestHandler):
  def do_GET(self):
    msg = """<!DOCTYPE html>
<html>
<body>
hello world
</body>
"""
    self.send_response(200)
    self.send_header('Content-Type', 'text/html')
    self.send_header('Content-Length', len(msg))
    self.end_headers()
    self.wfile.write(msg)

  def log_request(self, code='-', size='-'):
    pass

class SimpleLocalServerBackend(BaseHTTPServer.HTTPServer,
                               local_server.LocalServerBackend):
  def __init__(self):
    BaseHTTPServer.HTTPServer.__init__(
      self, ('127.0.0.1', 0), SimpleLocalServerBackendRequestHandler)
    local_server.LocalServerBackend.__init__(self)

  def StartAndGetNamedPorts(self, args):
    assert 'hello' in args
    assert args['hello'] == 'world'
    return [local_server.NamedPort('http', self.server_address[1])]

  def ServeForever(self):
    self.serve_forever()

class SimpleLocalServer(local_server.LocalServer):
  def __init__(self):
    super(SimpleLocalServer, self).__init__(SimpleLocalServerBackend)

  def GetBackendStartupArgs(self):
    return {'hello': 'world'}

  @property
  def url(self):
    return self.forwarder.url + '/'

class LocalServerUnittest(tab_test_case.TabTestCase):
  def testLocalServer(self):
    server = SimpleLocalServer()
    self._browser.StartLocalServer(server)
    self.assertTrue(server in self._browser.local_servers)
    self._tab.Navigate(server.url)
    self._tab.WaitForDocumentReadyStateToBeComplete()
    body_text = self._tab.EvaluateJavaScript('document.body.textContent')
    body_text = body_text.strip()
    self.assertEquals('hello world', body_text)

  def testStartingAndRestarting(self):
    server1 = SimpleLocalServer()
    self._browser.StartLocalServer(server1)

    server2 = SimpleLocalServer()
    self.assertRaises(Exception,
                      lambda: self._browser.StartLocalServer(server2))

    server1.Close()
    self.assertTrue(server1 not in self._browser.local_servers)

    self._browser.StartLocalServer(server2)
