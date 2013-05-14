#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import os
import sys
import time
from build import generate_deps_js_contents as deps_generator

import SimpleHTTPServer
import BaseHTTPServer

DEFAULT_PORT = 8003
DEPS_CHECK_DELAY = 30

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)

  def do_GET(self):
    if self.path == '/deps.js':
      current_time = time.time()
      if self.server.next_deps_check < current_time:
        self.log_message('Regenerating ' + self.path)
        self.server.deps = deps_generator.generate_deps_js()
        self.server.next_deps_check = current_time + DEPS_CHECK_DELAY

      self.send_response(200)
      self.send_header('Content-Type', 'application/javascript')
      self.send_header('content-Length', len(self.server.deps))
      self.end_headers()
      self.wfile.write(self.server.deps)
      return

    return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

  def log_error(self, format, *args):
    if self.path == '/favicon.ico':
      return
    self.log_message("While processing %s: ", self.path)

  def log_request(self, code='-', size='-'):
    # Dont spam the console unless it is important.
    pass


class Server(BaseHTTPServer.HTTPServer):
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
  sys.exit(Main(sys.argv[1:]))
