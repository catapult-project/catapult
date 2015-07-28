#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import os
import sys

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing import tracing_project

from build import dev_server


def getFilesIn(basedir):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(basedir, followlinks=True):
    new_dirnames = [d for d in dirnames if not d.startswith('.')]
    del dirnames[:]
    dirnames += new_dirnames

    for f in filenames:
      if f.startswith('.'):
        continue
      if f == 'README.md':
        continue
      full_f = os.path.join(dirpath, f)
      rel_f = os.path.relpath(full_f, basedir)
      data_files.append(rel_f)

  data_files.sort()
  return data_files


def do_GET_json_examples(request):
  data_files = getFilesIn(request.server.data_dir)
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)


def do_GET_json_examples_skp(request):
  data_files = getFilesIn(request.server.skp_data_dir)
  files_as_json = json.dumps(data_files)

  request.send_response(200)
  request.send_header('Content-Type', 'application/json')
  request.send_header('Content-Length', len(files_as_json))
  request.end_headers()
  request.wfile.write(files_as_json)


def do_GET_json_tests(self):
  test_module_resources = self.server.project.FindAllTestModuleResources()

  test_relpaths = [x.unix_style_relative_path
                   for x in test_module_resources]

  tests = {'test_relpaths': test_relpaths}
  tests_as_json = json.dumps(tests)

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
  project = tracing_project.TracingProject()

  parser = argparse.ArgumentParser(description='Run tracing development server')
  parser.add_argument(
      '-d', '--data-dir',
      default=os.path.abspath(os.path.join(project.test_data_path)))
  parser.add_argument(
      '-s', '--skp-data-dir',
      default=os.path.abspath(os.path.join(project.skp_data_path)))
  parser.add_argument('-p', '--port', default=8003, type=int)
  args = parser.parse_args(args=args)

  server = dev_server.DevServer(port=args.port, project=project)
  server.data_dir = os.path.abspath(args.data_dir)
  server.skp_data_dir = os.path.abspath(args.skp_data_dir)
  project.source_paths.append(server.data_dir)

  server.AddPathHandler('/json/examples', do_GET_json_examples)
  server.AddPathHandler('/tr/json/tests', do_GET_json_tests)
  server.AddPathHandler('/json/examples/skp', do_GET_json_examples_skp)

  server.AddSourcePathMapping(project.tracing_root_path)

  server.AddPathHandler('/test_automation/notify_test_result',
                        do_POST_report_test_results, supports_post=True)
  server.AddPathHandler('/test_automation/notify_completion',
                        do_POST_report_test_completion, supports_post=True)

  server.serve_forever()
