#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import sys

from trace_viewer import trace_viewer_project
import tvcm

_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def getFilesIn(basedir):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(basedir, followlinks=True):
    new_dirnames = [d for d in dirnames if not d.startswith('.')]
    del dirnames[:]
    dirnames += new_dirnames

    for f in filenames:
      if f.startswith('.'):
        continue
      full_f = os.path.join(dirpath, f)
      rel_f = os.path.relpath(full_f, basedir)
      data_files.append(rel_f)

  data_files.sort()
  return data_files


def do_GET_json_examples(request):
  test_data_path = os.path.abspath(os.path.join(_ROOT_PATH, 'test_data'))
  data_files = getFilesIn(test_data_path)
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)

def do_GET_json_examples_skp(request):
  skp_data_path = os.path.abspath(os.path.join(_ROOT_PATH, 'skp_data'))
  data_files = getFilesIn(skp_data_path)
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)

def do_GET_json_tests(self):
  test_module_resources = self.server.project.FindAllTestModuleResources()

  test_module_names = [x.name for x in test_module_resources]

  tests = {'test_module_names': test_module_names,
           'test_links': self.server.test_links}
  tests_as_json = json.dumps(tests);

  self.send_response(200)
  self.send_header('Content-Type', 'application/json')
  self.send_header('Content-Length', len(tests_as_json))
  self.end_headers()
  self.wfile.write(tests_as_json)

def do_POST_report_test_results(request):
  request.send_response(200)
  request.send_header('Content-Length', '0')
  request.end_headers()
  msg = request.rfile.read()
  ostream = sys.stdout if 'PASSED' in msg else sys.stderr
  ostream.write(msg + '\n')

def do_POST_report_test_completion(request):
  request.send_response(200)
  request.send_header('Content-Length', '0')
  request.end_headers()
  msg = request.rfile.read()
  sys.stdout.write(msg + '\n')
  request.server.RequestShutdown(exit_code=(0 if 'ALL_PASSED' in msg else 1))

def Main(args):
  port = 8003
  project = trace_viewer_project.TraceViewerProject()

  server = tvcm.DevServer(port=port, project=project)
  server.AddPathHandler('/json/examples', do_GET_json_examples)
  server.AddPathHandler('/tv/json/tests', do_GET_json_tests)
  server.AddPathHandler('/json/examples/skp', do_GET_json_examples_skp)

  server.AddSourcePathMapping(project.trace_viewer_path)
  server.AddTestLink('/examples/skia_debugger.html', 'Skia Debugger')
  server.AddTestLink('/examples/trace_viewer.html', 'Trace File Viewer')

  server.AddPathHandler('/test_automation/notify_test_result',
                        do_POST_report_test_results, supports_post=True)
  server.AddPathHandler('/test_automation/notify_completion',
                        do_POST_report_test_completion, supports_post=True)


  server.serve_forever()
