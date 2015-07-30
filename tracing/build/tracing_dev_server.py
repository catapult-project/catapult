# Copyright (c) 2015 The Chromium Authors. All rights reserved.
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

from paste import httpserver
from paste import fileapp

import webapp2
from webapp2 import Route, RedirectHandler

def _GetFilesIn(basedir):
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


class TestListHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs):
    test_module_resources = self.app.project.FindAllTestModuleResources()

    test_relpaths = [x.unix_style_relative_path
                     for x in test_module_resources]

    tests = {'test_relpaths': test_relpaths}
    tests_as_json = json.dumps(tests)
    self.response.content_type = 'application/json'
    return self.response.write(tests_as_json)


class TestResultHandler(webapp2.RequestHandler):
  def post(self, *args, **kwargs):
    msg = self.request.body
    ostream = sys.stdout if 'PASSED' in msg else sys.stderr
    ostream.write(msg + '\n')
    return self.response.write('')


class TestsCompletedHandler(webapp2.RequestHandler):
  def post(self, *args, **kwargs):
    msg = self.request.body
    sys.stdout.write(msg + '\n')
    exit_code=(0 if 'ALL_PASSED' in msg else 1)
    if hasattr(self.app.server, 'please_exit'):
      self.app.server.please_exit(exit_code)
    return self.response.write('')


class DirectoryListingHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs):
    source_path = kwargs.pop('_source_path', None)
    mapped_path = kwargs.pop('_mapped_path', None)
    assert mapped_path.endswith('/')

    data_files_relative_to_top = _GetFilesIn(source_path)
    data_files = [mapped_path + x
                  for x in data_files_relative_to_top]

    files_as_json = json.dumps(data_files)
    self.response.content_type = 'application/json'
    return self.response.write(files_as_json)


class SourcePathsHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs):
    source_paths = kwargs.pop('_source_paths', [])

    path = self.request.path

    # This is how we do it. Its... strange, but its what we've done since
    # the dawn of time. Aka 4 years ago, lol.
    for mapped_path in source_paths:
      rel = os.path.relpath(path, '/')
      candidate = os.path.join(mapped_path, rel)
      if os.path.exists(candidate):
        app = fileapp.FileApp(candidate)
        app.cache_control(no_cache=True)
        return app
    self.abort(404)


def CreateApp(project=None,
              test_data_path=None,
              skp_data_path=None):
  if project is None:
    project = tracing_project.TracingProject()

  routes = [
    Route('', RedirectHandler, defaults={'_uri': '/base/tests.html'}),
    Route('/', RedirectHandler, defaults={'_uri': '/base/tests.html'}),
    Route('/tr/json/tests', TestListHandler),
    Route('/tr/json/notify_test_result', TestResultHandler),
    Route('/tr/json/notify_tests_completed', TestsCompletedHandler)
  ]


  # Test data system.
  if not test_data_path:
    test_data_path = project.test_data_path
  routes.append(Route('/test_data/__file_list__', DirectoryListingHandler,
                      defaults={
                          '_source_path': test_data_path,
                          '_mapped_path': '/test_data/'
                      }))

  if not skp_data_path:
    skp_data_path = project.skp_data_path
  routes.append(Route('/skp_data/__file_list__', DirectoryListingHandler,
                      defaults={
                          '_source_path': skp_data_path,
                          '_mapped_path': '/skp_data/'
                      }))

  # This must go last, because its catch-all.
  #
  # Its funky that we have to add in the root path. The long term fix is to
  # stop with the crazy multi-source-pathing thing.
  all_paths = list(project.source_paths) + [project.tracing_root_path]
  routes.append(
    Route('/<:.+>', SourcePathsHandler,
          defaults={'_source_paths': all_paths}))

  app = webapp2.WSGIApplication(routes=routes, debug=True)
  app.project = project
  return app

def _AddPleaseExitMixinToServer(server):
  # Shutting down httpserver gracefully and yielding a return code requires
  # a bit of mixin code.

  exitCodeAttempt = []
  def please_exit(exitCode):
    if len(exitCodeAttempt) > 0:
      return
    exitCodeAttempt.append(exitCode)
    server.running = False

  real_serve_forever = server.serve_forever

  def serve_forever():
    try:
      real_serve_forever()
    except KeyboardInterrupt:
        # allow CTRL+C to shutdown
        return 255

    if len(exitCodeAttempt) == 1:
      return exitCodeAttempt[0]
    # The serve_forever returned for some reason separate from
    # exit_please.
    return 0

  server.please_exit = please_exit
  server.serve_forever = serve_forever



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

  app = CreateApp(project,
                  test_data_path=args.data_dir,
                  skp_data_path=args.skp_data_dir)

  server = httpserver.serve(app, host='127.0.0.1', port=args.port,
                            start_loop=False)
  _AddPleaseExitMixinToServer(server)
  app.server = server

  sys.stderr.write('Now running on http://127.0.0.1:%i\n' % args.port)

  return server.serve_forever()
