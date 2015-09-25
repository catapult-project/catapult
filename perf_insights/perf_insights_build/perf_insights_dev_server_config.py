# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys

import perf_insights_project

import webapp2
from webapp2 import Route

from perf_insights import local_directory_corpus_driver
from perf_insights import corpus_query
from perf_insights import map_runner
from perf_insights import map_function_handle as map_function_handle_module
from perf_insights import progress_reporter
from perf_insights.results import json_output_formatter


def _RelPathToUnixPath(p):
  return p.replace(os.sep, '/')

class TestListHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs): # pylint: disable=unused-argument
    project = perf_insights_project.PerfInsightsProject()
    test_relpaths = ['/' + _RelPathToUnixPath(x)
                     for x in project.FindAllTestModuleRelPaths()]

    tests = {'test_relpaths': test_relpaths}
    tests_as_json = json.dumps(tests)
    self.response.content_type = 'application/json'
    return self.response.write(tests_as_json)


class RunMapFunctionHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs): # pylint: disable=unused-argument
    map_function = kwargs.pop('map_function')

    map_function_handle = map_function_handle_module.MapFunctionHandle(
      map_function_name=map_function)

    pi_data_dir = kwargs.pop('_pi_data_dir')
    corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
        pi_data_dir)

    # TODO(nduca): pass self.request.params to the map function [maybe].
    query_string = self.request.params.get('corpus_query', 'True')
    query = corpus_query.CorpusQuery.FromString(query_string)

    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)

    self._RunMapper(trace_handles, map_function_handle)

  def _RunMapper(self, trace_handles, map_function_handle):
    self.response.content_type = 'application/json'
    output_formatter = json_output_formatter.JSONOutputFormatter(
        self.response.out)

    runner = map_runner.MapRunner(
        trace_handles, map_function_handle)
    runner.Run(jobs=map_runner.AUTO_JOB_COUNT,
               output_formatters=[output_formatter])


class PerfInsightsDevServerConfig(object):
  def __init__(self):
    self.project = perf_insights_project.PerfInsightsProject()

  def GetName(self):
    return 'perf_insights'

  def GetRunUnitTestsUrl(self):
    return '/perf_insights/tests.html'

  def AddOptionstToArgParseGroup(self, g):
    g.add_argument('--pi-data-dir',
                   default=self.project.perf_insights_test_data_path)

  def GetRoutes(self, args):  # pylint: disable=unused-argument
    return [
      Route('/perf_insights/tests', TestListHandler),
      Route('/perf_insights_examples/run_map_function/<map_function:.+>',
            RunMapFunctionHandler,
            defaults={
              '_pi_data_dir':
                  os.path.abspath(os.path.expanduser(args.pi_data_dir))
            })
    ]

  def GetSourcePaths(self, args):  # pylint: disable=unused-argument
    return list(self.project.source_paths)

  def GetTestDataPaths(self, args):  # pylint: disable=unused-argument
    return [('/perf_insights/test_data/',
             args.pi_data_dir)]

