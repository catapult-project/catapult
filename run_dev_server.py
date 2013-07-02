#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import optparse
import os
import sys
import time
import traceback
from build import generate_deps_js_contents as deps_generator
from build import generate_template_contents as template_generator

import SocketServer
import SimpleHTTPServer
import BaseHTTPServer

DEFAULT_PORT = 8003
DEPS_CHECK_DELAY = 30

toplevel_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.join(toplevel_dir, 'src')
test_data_dir = os.path.join(toplevel_dir, 'test_data')

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)

  def send_response(self, code, message=None):
    SimpleHTTPServer.SimpleHTTPRequestHandler.send_response(self, code, message)
    if code == 200:
      self.send_header('Cache-Control', 'no-cache')

  def do_GET_json_tests(self):
    def is_test(x):
      basename = os.path.basename(x)
      if basename.startswith('.'):
        return False

      if basename.endswith('_test.js'):
        return True
      return False

    test_filenames = []
    for dirpath, dirnames, filenames in os.walk(src_dir):
      for f in filenames:
        x = os.path.join(dirpath, f)
        y = '/' + os.path.relpath(x, toplevel_dir)
        if is_test(y):
          test_filenames.append(y)

    test_filenames.sort()

    tests_as_json = json.dumps(test_filenames)

    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.send_header('Content-Length', len(tests_as_json))
    self.end_headers()
    self.wfile.write(tests_as_json)

  def do_GET_example_files(self):
    data_files = []
    for dirpath, dirnames, filenames in os.walk(test_data_dir):
      for f in filenames:
        data_files.append(f)

    data_files.sort()
    files_as_json = json.dumps(data_files)

    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.send_header('Content-Length', len(files_as_json))
    self.end_headers()
    self.wfile.write(files_as_json)

  def do_GET_deps(self):
    current_time = time.time()
    if self.server.next_deps_check < current_time:
      self.log_message('Regenerating ' + self.path)
      try:
        self.server.deps = deps_generator.generate_deps_js()
      except Exception, ex:
        msg = json.dumps({"details": traceback.format_exc(),
                          "message": ex.message});
        self.log_error('While parsing deps: %s', ex.message)
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', len(msg))
        self.end_headers()
        self.wfile.write(msg)
        return

      self.server.next_deps_check = current_time + DEPS_CHECK_DELAY

    self.send_response(200)
    self.send_header('Content-Type', 'application/javascript')
    self.send_header('Content-Length', len(self.server.deps))
    self.end_headers()
    self.wfile.write(self.server.deps)

  def do_GET_templates(self):
    templates = template_generator.generate_templates()

    self.send_response(200)
    self.send_header('Content-Type', 'text/html')
    self.send_header('Content-Length', len(templates))
    self.end_headers()
    self.wfile.write(templates)

  def do_GET(self):
    if self.path == '/json/examples':
      self.do_GET_example_files()
      return

    if self.path == '/json/tests':
      self.do_GET_json_tests()
      return

    if self.path == '/templates':
      self.do_GET_templates()
      return

    if self.path == '/deps.js':
      self.do_GET_deps()
      return

    return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

  def log_error(self, format, *args):
    if self.path == '/favicon.ico':
      return
    self.log_message("While processing %s: ", self.path)
    SimpleHTTPServer.SimpleHTTPRequestHandler.log_error(self, format, *args)

  def log_request(self, code='-', size='-'):
    # Dont spam the console unless it is important.
    pass


class Server(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
  def __init__(self, *args, **kwargs):
    BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
    self.next_deps_check = -1
    self.deps = None

def Main(args):
  parser = optparse.OptionParser()
  parser.add_option('--port',
                    action='store',
                    type='int',
                    default=DEFAULT_PORT,
                    help='Port to serve from')
  options, args = parser.parse_args()
  server = Server(('', options.port), Handler)
  sys.stderr.write("Now running on http://localhost:%i\n" % options.port)
  server.serve_forever()

if __name__ == '__main__':
  os.chdir(toplevel_dir)
  sys.exit(Main(sys.argv[1:]))
