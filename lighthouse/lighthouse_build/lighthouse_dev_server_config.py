# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

import lighthouse_project

import webapp2
from webapp2 import Route


def _RelPathToUnixPath(p):
  return p.replace(os.sep, '/')

class TestListHandler(webapp2.RequestHandler):
  def get(self, *args, **kwargs): # pylint: disable=unused-argument
    project = lighthouse_project.LighthouseProject()
    test_relpaths = ['/' + _RelPathToUnixPath(x)
                     for x in project.FindAllTestModuleRelPaths()]

    tests = {'test_relpaths': test_relpaths}
    tests_as_json = json.dumps(tests)
    self.response.content_type = 'application/json'
    return self.response.write(tests_as_json)


class LighthouseDevServerConfig(object):
  def __init__(self):
    self.project = lighthouse_project.LighthouseProject()

  def GetName(self):
    return 'lighthouse'

  def GetRunUnitTestsUrl(self):
    return '/lighthouse/tests.html'

  def AddOptionstToArgParseGroup(self, g):
    pass

  def GetRoutes(self, args):  # pylint: disable=unused-argument
    return [
        Route('/lighthouse/tests', TestListHandler)
    ]

  def GetSourcePaths(self, args):  # pylint: disable=unused-argument
    return list(self.project.source_paths)

  def GetTestDataPaths(self, args):  # pylint: disable=unused-argument
    return []
