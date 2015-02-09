#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import json
import optparse
import os
import socket
import sys
import time
import traceback

from tvcm import project as project_module
from tvcm import generate
from tvcm import resource_loader

import SocketServer
import SimpleHTTPServer
import StringIO
import BaseHTTPServer

RELOAD_CHECK_DELAY = 30

class DevServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)

  def send_response(self, code, message=None):
    SimpleHTTPServer.SimpleHTTPRequestHandler.send_response(self, code, message)
    if code == 200:
      self.send_header('Cache-Control', 'no-cache')

  def do_GET(self):
    try:
      self.server.ReloadProjectIfNeeded()
    except Exception, ex:
      send_500(self, "While processing project files", ex, path=self.path)
      return

    if self.do_path_handler('GET'):
      return

    return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

  def do_POST(self):
    if self.do_path_handler('POST'):
      return
    return SimpleHTTPServer.SimpleHTTPRequestHandler.do_POST(self)


  def do_path_handler(self, method):
    handler = self.server.GetPathHandler(self.path, method)
    if handler:
      try:
        handler(self)
      except Exception, ex:
        send_500(self, "While parsing %s" % self.path, ex, path=self.path)
      return True
    return False

  def send_head(self):
    return SimpleHTTPServer.SimpleHTTPRequestHandler.send_head(self)

  def translate_path(self, path):
    path = path.split('?',1)[0]
    path = path.split('#',1)[0]
    for mapped_path in self.server.project.source_paths:
      rel = os.path.relpath(path, '/')
      candidate = os.path.join(mapped_path, rel)
      if os.path.exists(candidate):
        return candidate
    return ''

  def log_error(self, format, *args):
    if self.server._quiet:
      return
    if self.path == '/favicon.ico':
      return
    self.log_message("While processing %s: ", self.path)
    SimpleHTTPServer.SimpleHTTPRequestHandler.log_error(self, format, *args)

  def log_request(self, code='-', size='-'):
    # Dont spam the console unless it is important.
    pass

  def finish(self):
    try:
      SimpleHTTPServer.SimpleHTTPRequestHandler.finish(self)
    except socket.error:
        # An final socket error may have occurred here, such as
        # the local error ECONNABORTED.
        pass

def do_GET_json_tests(self):
  test_module_resources = self.server.project.FindAllTestModuleResources()
  if self.server.test_module_resource_filter:
    cur_filter = self.server.test_module_resource_filter
  else:
    cur_filter = lambda x: True

  test_module_names = [x.name for x in test_module_resources if cur_filter(x)]

  tests = {'test_module_names': test_module_names,
           'test_links': self.server.test_links}
  tests_as_json = json.dumps(tests);

  self.send_response(200)
  self.send_header('Content-Type', 'application/json')
  self.send_header('Content-Length', len(tests_as_json))
  self.end_headers()
  self.wfile.write(tests_as_json)

def send_500(self, msg, ex, log_error=True, path=None):
  if path == None:
    is_html_output = False
  else:
    path = path.split('?',1)[0]
    path = path.split('#',1)[0]
    is_html_output = path.endswith('.html')


  if is_html_output:
    msg = """<!DOCTYPE html>
    <html>
    <body>
    <h1>OMG something is wrong</h1>
    <b><pre><code id="message"></code></pre></b></p>
    <pre><code id="details"></code></pre>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
      document.querySelector('#details').textContent = %s;
      document.querySelector('#message').textContent = %s;
      });
    </script>
    </body>
    </html>
""" % (json.dumps(traceback.format_exc()), json.dumps(ex.message))
    ctype = 'text/html'
  else:
    msg = json.dumps({"details": traceback.format_exc(),
                      "message": ex.message});
    ctype = 'application/json'

  if log_error:
    self.log_error('%s: %s', msg, ex.message)
  self.send_response(500)
  self.send_header('Content-Type', ctype)
  self.send_header('Cache-Control', 'no-cache')
  self.send_header('Content-Length', len(msg))
  self.end_headers()
  self.wfile.write(msg)
  return

class PathHandler(object):
  def __init__(self, path, handler, supports_get, supports_post):
    self.path = path
    self.handler = handler
    self.supports_get = supports_get
    self.supports_post = supports_post

  def CanHandle(self, path, method):
    if path != self.path:
      return False
    if method == 'GET' and self.supports_get:
      return True
    if method == 'POST' and self.supports_post:
      return True
    return False

def do_GET_root(request):
  request.send_response(301)
  request.send_header("Location", request.server.default_path)
  request.end_headers()

class DevServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
  def __init__(self, port, quiet=False, project=None):
    BaseHTTPServer.HTTPServer.__init__(
        self, ('localhost', port), DevServerHandler)
    self._quiet = quiet
    if port == 0:
      port = self.server_address[1]
    self._port = port
    self._path_handlers = []
    self._test_links = []
    if project:
      self._project = project
    else:
      self._project = project_module.Project([])

    self._next_reload_check = -1
    self.test_module_resource_filter = None

    self.AddPathHandler('/', do_GET_root)
    self.AddPathHandler('', do_GET_root)
    self.default_path = '/base/tests.html'
    # Redirect old tests.html places to the new location until folks have gotten used to its new
    # location.
    self.AddPathHandler('/tvcm/tests.html', do_GET_root)
    self.AddPathHandler('/tests.html', do_GET_root)

    self.AddPathHandler('/tv/json/tests', do_GET_json_tests)

  def AddPathHandler(self, path, handler, supports_get=True, supports_post=False):
    self._path_handlers.append(PathHandler(path, handler, supports_get, supports_post))

  def GetPathHandler(self, path, method):
    for h in self._path_handlers:
      if h.CanHandle(path, method):
        return h.handler
    return None

  def SetTestFilterToAllowOnlyFilenamesMatching(self, x):
    def FilterOnX(r):
      return x in r.name
    self.test_module_resource_filter = FilterOnX

  def AddSourcePathMapping(self, file_system_path):
    self._project.AddSourcePath(file_system_path)

  def AddTestLink(self, path, title):
    self._test_links.append({'path': path,
                             'title': title})

  @property
  def test_links(self):
    return self._test_links

  @property
  def project(self):
    return self._project

  @property
  def loader(self):
    return self._project.loader

  def ReloadProjectIfNeeded(self):
    current_time = time.time()
    if self._next_reload_check >= current_time:
      return

    if not self._quiet:
      sys.stderr.write('Reloading project to check for errors...\n')

    self.project.ResetLoader()
    load_sequence = self.project.CalcLoadSequenceForAllModules()
    self._next_reload_check = current_time + RELOAD_CHECK_DELAY

  @property
  def port(self):
    return self._port

  def serve_forever(self):
    if not self._quiet:
      sys.stderr.write("Now running on http://localhost:%i\n" % self._port)
    BaseHTTPServer.HTTPServer.serve_forever(self)
