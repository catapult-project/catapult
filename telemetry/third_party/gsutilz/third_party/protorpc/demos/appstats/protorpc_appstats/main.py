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

import os
import re

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from protorpc.webapp import service_handlers

import protorpc_appstats

# This regular expression is used to extract the full path of
# an incoming request so that the service can be correctly
# registered with its internal registry.  The only assumption
# that is made about the placement of the appstats service by
# this main module is that the last element of the service path
# is 'service'.
_METHOD_REGEX = r'\.[^/]+'
_SERVICE_PATH_REGEX = re.compile(r'(.*)/service(%s|/protorpc(%s)?)?' %
                                 (_METHOD_REGEX, _METHOD_REGEX))


def parse_service_path(path_info):
  """Parse the service path from PATH_INFO in the environment.

  The appstats service may be placed at any URL path within a webapp
  application.  It isn't possible to know what the actual path is
  until the actual request time.  This function attempts to parse
  the incoming request to determine where the appstats service is
  configured.  If it can successfully determine its location, it
  will attempt to map protorpc RegistryService underneath its service
  path.

  The appstats service is always expected to be <path>/service.  The
  RegistryService is mapped to <path>/service/protorpc.

  Args:
    path_info: PATH_INFO extracted from the CGI environment.

  Returns:
    A pair paths (appstats_service_path, registry_service_path):
      appstats_service_path: The full path of the appstats service.  If the
        full path cannot be determined this will be '.*/service'.
      registry_service_path: The full path of the appstats registry service.
        If the path of the appstats service cannot be determined this will be
        None.
  """
  match = _SERVICE_PATH_REGEX.match(path_info)
  if match:
    appstats_service_path = '%s/service' % (match.group(1),)
    # Creates a "local" registry service.
    registry_service_path = '%s/protorpc' % (appstats_service_path,)
  else:
    # Not possible to determine full service name for registry.  Do
    # not create registry for service.
    appstats_service_path = '.*/service'
    registry_service_path = None
  return appstats_service_path, registry_service_path


def main():
  path_info = os.environ.get('PATH_INFO', '')
  service_path, registry_path = parse_service_path(path_info)

  # Create webapp URL mappings for service and private registry.
  mapping = service_handlers.service_mapping(
    [(service_path, protorpc_appstats.AppStatsService)], registry_path)

  application = webapp.WSGIApplication(mapping)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
