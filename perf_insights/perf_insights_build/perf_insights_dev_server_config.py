# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys

import perf_insights_project

import webapp2
from webapp2 import Route


def _RelPathToUnixPath(p):
  return p.replace(os.sep, '/')

class TestListHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs):  # pylint: disable=unused-argument
    project = perf_insights_project.PerfInsightsProject()
    test_relpaths = ['/' + _RelPathToUnixPath(x)
                     for x in project.FindAllTestModuleRelPaths()]

    tests = {'test_relpaths': test_relpaths}
    tests_as_json = json.dumps(tests)
    self.response.content_type = 'application/json'
    return self.response.write(tests_as_json)


class PerfInsightsDevServerConfig(object):
  def __init__(self):
    self.project = perf_insights_project.PerfInsightsProject()

  def GetName(self):
    return 'perf_insights'

  def GetRunUnitTestsUrl(self):
    return '/perf_insights/tests.html'

  def AddOptionstToArgParseGroup(self, g):  # pylint: disable=unused-argument
    pass

  def GetRoutes(self, args):  # pylint: disable=unused-argument
    return [Route('/perf_insights/tests', TestListHandler)]

  def GetSourcePaths(self, args):  # pylint: disable=unused-argument
    return list(self.project.source_paths)

  def GetTestDataPaths(self, args):  # pylint: disable=unused-argument
    return [('/perf_insights/test_data/',
             self.project.perf_insights_test_data_path)]

