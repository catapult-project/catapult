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
import base64
from build import parse_deps
from build import generate

import SocketServer
import SimpleHTTPServer
import BaseHTTPServer

DEFAULT_PORT = 8003
DEPS_CHECK_DELAY = 30

toplevel_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.join(toplevel_dir, 'src')
test_data_dir = os.path.join(toplevel_dir, 'test_data')
skp_data_dir = os.path.join(toplevel_dir, 'skp_data')

def find_all_js_module_filenames(search_paths):
  all_filenames = []

  def ignored(x):
    if os.path.basename(x).startswith('.'):
      return True
    if os.path.splitext(x)[1] != ".js":
      return True
    return False

  for search_path in search_paths:
    for dirpath, dirnames, filenames in os.walk(search_path):
      for f in filenames:
        x = os.path.join(dirpath, f)
        if ignored(x):
          continue
        all_filenames.append(os.path.relpath(x, search_path))

  return all_filenames

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

  def do_GET_example_skp_files(self):
    data_files = []
    for dirpath, dirnames, filenames in os.walk(skp_data_dir):
      for f in filenames:
        data_files.append(f)

    data_files.sort()
    files_as_json = json.dumps(data_files)

    self.send_response(200)
    self.send_header('Content-Type', 'application/json')
    self.send_header('Content-Length', len(files_as_json))
    self.end_headers()
    self.wfile.write(files_as_json)

  def do_GET_skp_file(self):
    with open(toplevel_dir + self.path, 'r') as content_file:
      content = content_file.read()

    b64_file = base64.b64encode(content)

    self.send_response(200)
    self.send_header('Content-Type', 'text/plain')
    self.send_header('Content-Length', len(b64_file))
    self.end_headers()
    self.wfile.write(b64_file)

  def do_GET_deps(self):
    try:
      self.server.update_deps_and_templates()
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
    self.send_response(200)
    self.send_header('Content-Type', 'application/javascript')
    self.send_header('Content-Length', len(self.server.deps))
    self.end_headers()
    self.wfile.write(self.server.deps)

  def do_GET_templates(self):
    self.server.update_deps_and_templates()
    self.send_response(200)
    self.send_header('Content-Type', 'text/html')
    self.send_header('Content-Length', len(self.server.templates))
    self.end_headers()
    self.wfile.write(self.server.templates)

  def do_GET(self):
    if self.path == '/json/examples':
      self.do_GET_example_files()
      return

    if self.path == '/json/examples/skp':
      self.do_GET_example_skp_files()
      return

    if self.path == '/json/tests':
      self.do_GET_json_tests()
      return

    if self.path.startswith('/skp_data'):
      self.do_GET_skp_file()
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

  def update_deps_and_templates(self):
    current_time = time.time()
    if self.next_deps_check >= current_time:
      return
    print 'Regenerating deps and templates'
    all_js_module_filenames = find_all_js_module_filenames([src_dir])
    load_sequence = parse_deps.calc_load_sequence(
        all_js_module_filenames, [src_dir])
    self.deps = generate.generate_deps_js(load_sequence)
    self.templates = generate.generate_html_for_combined_templates(
        load_sequence)
    self.next_deps_check = current_time + DEPS_CHECK_DELAY

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
