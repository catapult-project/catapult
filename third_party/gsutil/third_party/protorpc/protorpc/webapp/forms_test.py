#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for protorpc.forms."""

__author__ = 'rafek@google.com (Rafe Kaplan)'


import os
import unittest

from protorpc import test_util
from protorpc import webapp_test_util
from protorpc.webapp import forms
from protorpc.webapp.google_imports import template


class ModuleInterfaceTest(test_util.ModuleInterfaceTest,
                          test_util.TestCase):

  MODULE = forms


def RenderTemplate(name, **params):
  """Load content from static file.

  Args:
    name: Name of static file to load from static directory.
    params: Passed in to webapp template generator.

  Returns:
    Contents of static file.
  """
  path = os.path.join(forms._TEMPLATES_DIR, name)
  return template.render(path, params)


class ResourceHandlerTest(webapp_test_util.RequestHandlerTestBase):

  def CreateRequestHandler(self):
    return forms.ResourceHandler()

  def DoStaticContentTest(self, name, expected_type):
    """Run the static content test.

    Loads expected static content from source and compares with
    results in response.  Checks content-type and cache header.

    Args:
      name: Name of file that should be served.
      expected_type: Expected content-type of served file.
    """
    self.handler.get(name)

    content = RenderTemplate(name)
    self.CheckResponse('200 OK',
                       {'content-type': expected_type,
                       },
                       content)

  def testGet(self):
    self.DoStaticContentTest('forms.js', 'text/javascript')

  def testNoSuchFile(self):
    self.handler.get('unknown.txt')

    self.CheckResponse('404 Not Found',
                       {},
                       'Resource not found.')


class FormsHandlerTest(webapp_test_util.RequestHandlerTestBase):

  def CreateRequestHandler(self):
    handler = forms.FormsHandler('/myreg')
    self.assertEquals('/myreg', handler.registry_path)
    return handler

  def testGetForm(self):
    self.handler.get()

    content = RenderTemplate(
        'forms.html',
        forms_path='/tmp/myhandler',
        hostname=self.request.host,
        registry_path='/myreg')

    self.CheckResponse('200 OK',
                       {},
                       content)

  def testGet_MissingPath(self):
    self.ResetHandler({'QUERY_STRING': 'method=my_method'})

    self.handler.get()

    content = RenderTemplate(
        'forms.html',
        forms_path='/tmp/myhandler',
        hostname=self.request.host,
        registry_path='/myreg')

    self.CheckResponse('200 OK',
                       {},
                       content)

  def testGet_MissingMethod(self):
    self.ResetHandler({'QUERY_STRING': 'path=/my-path'})

    self.handler.get()

    content = RenderTemplate(
        'forms.html',
        forms_path='/tmp/myhandler',
        hostname=self.request.host,
        registry_path='/myreg')

    self.CheckResponse('200 OK',
                       {},
                       content)

  def testGetMethod(self):
    self.ResetHandler({'QUERY_STRING': 'path=/my-path&method=my_method'})

    self.handler.get()

    content = RenderTemplate(
        'methods.html',
        forms_path='/tmp/myhandler',
        hostname=self.request.host,
        registry_path='/myreg',
        service_path='/my-path',
        method_name='my_method')

    self.CheckResponse('200 OK',
                       {},
                       content)


def main():
  unittest.main()


if __name__ == '__main__':
  main()
