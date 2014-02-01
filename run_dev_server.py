#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import json

import build # Brings in tvcm bindings.
import tvcm

toplevel_path = os.path.abspath(os.path.dirname(__file__))
tvcm_path = os.path.join(toplevel_path, 'third_party', 'tvcm')
src_path = os.path.join(toplevel_path, 'src')
test_data_path = os.path.join(toplevel_path, 'test_data')
skp_data_path = os.path.join(toplevel_path, 'skp_data')

def do_GET_json_examples(request):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(test_data_path):
    for f in filenames:
      data_files.append(f)

  data_files.sort()
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)

def do_GET_json_examples_skp(request):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(skp_data_path):
    for f in filenames:
      data_files.append(f)

  data_files.sort()
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)

def Main(port, args):
  server = tvcm.DevServer(port=port)
  server.AddPathHandler('/json/examples', do_GET_json_examples)
  server.AddPathHandler('/json/examples/skp', do_GET_json_examples_skp)

  server.AddSourcePathMapping(tvcm_path)
  server.AddSourcePathMapping(src_path)
  server.AddDataPathMapping(os.path.join(toplevel_path, 'third_party'))
  server.AddDataPathMapping(toplevel_path)
  server.serve_forever()

if __name__ == '__main__':
  sys.exit(Main(port=8003, args=sys.argv[1:]))
