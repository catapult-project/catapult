# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import BaseHTTPServer
import mimetypes
import os
import SimpleHTTPServer
import SocketServer
import sys
import zlib


class MemoryCacheHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

  def do_GET(self):
    """Serve a GET request."""
    resource = self.SendHead()
    if resource:
      self.wfile.write(resource['response'])

  def do_HEAD(self):
    """Serve a HEAD request."""
    self.SendHead()

  def SendHead(self):
    path = self.translate_path(self.path)
    ctype = self.guess_type(path)
    if path not in self.server.resource_map:
      self.send_error(404, 'File not found')
      return None
    resource = self.server.resource_map[path]
    self.send_response(200)
    self.send_header('Content-Type', ctype)
    self.send_header('Content-Length', str(resource['content-length']))
    self.send_header('Last-Modified',
                     self.date_time_string(resource['last-modified']))
    if resource['zipped']:
      self.send_header('Content-Encoding', 'deflate')
    self.end_headers()
    return resource


class MemoryCacheHTTPServer(SocketServer.ThreadingMixIn,
                            BaseHTTPServer.HTTPServer):
  # Increase the request queue size. The default value, 5, is set in
  # SocketServer.TCPServer (the parent of BaseHTTPServer.HTTPServer).
  # Since we're intercepting many domains through this single server,
  # it is quite possible to get more than 5 concurrent requests.
  request_queue_size = 128

  def __init__(self, host_port, handler, directories):
    BaseHTTPServer.HTTPServer.__init__(self, host_port, handler)
    self.resource_map = {}
    for path in directories:
      self.LoadResourceMap(path)

  def LoadResourceMap(self, cwd):
    """Loads all files in cwd into the in-memory resource map."""
    for root, dirs, files in os.walk(cwd):
      # Skip hidden files and folders (like .svn and .git).
      files = [f for f in files if f[0] != '.']
      dirs[:] = [d for d in dirs if d[0] != '.']

      for f in files:
        file_path = os.path.join(root, f)
        if not os.path.exists(file_path):  # Allow for '.#' files
          continue
        with open(file_path, 'rb') as fd:
          response = fd.read()
          fs = os.fstat(fd.fileno())
          content_type = mimetypes.guess_type(file_path)[0]
          zipped = False
          if content_type in ['text/html', 'text/css',
                              'application/javascript']:
            zipped = True
            response = zlib.compress(response, 9)
          self.resource_map[file_path] = {
            'content-length': len(response),
            'last-modified': fs.st_mtime,
            'response': response,
            'zipped': zipped
            }


def Main():
  assert len(sys.argv) > 2, 'usage: %prog <port> [<path1>, <path2>, ...]'

  port = int(sys.argv[1])
  directories = sys.argv[2:]
  server_address = ('127.0.0.1', port)
  MemoryCacheHTTPRequestHandler.protocol_version = 'HTTP/1.1'
  httpd = MemoryCacheHTTPServer(server_address, MemoryCacheHTTPRequestHandler,
                                directories)
  httpd.serve_forever()


if __name__ == '__main__':
  Main()
