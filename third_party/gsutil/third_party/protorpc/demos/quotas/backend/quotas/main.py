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

"""Quota service main handler.

Hosts a QuotaServer ProtoRPC service.  This application is intended for use
as a backend server only.  The service is configured based on a
configuration file loaded from a quotas.json in the backend application
directory.  The quotas.json file is a JSON encoded
quotas.service.QuotaConfig ProtoRPC message.
"""

from __future__ import with_statement

import os
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from protorpc import protojson
from protorpc.webapp import service_handlers

from quotas import services

APP_DIR = os.path.dirname(os.path.dirname(os.environ['PATH_TRANSLATED']))
QUOTA_CONFIG_PATH = os.path.join(APP_DIR, 'quotas.json')


def load_quota_config(quota_config_path=QUOTA_CONFIG_PATH):
  """Load quota configuration from from file.

  Args:
    quota_config_path: Quota to configuration file.  Contents of file must be
      a JSON encoded ProtoRPC message of the format defined by
      quota.services.QuotaConfig.

    Returns:
      quota.services.QuotaConfig instance with contents parsed from quota file.
  """
  with open(quota_config_path) as quota_config_file:
    encoded_config = quota_config_file.read()
  return protojson.decode_message(services.QuotaConfig, encoded_config)

service_mappings = service_handlers.service_mapping(
  [
    ('/quota-service',
     services.QuotaService.new_factory(load_quota_config(), {})),
  ])

application = webapp.WSGIApplication(service_mappings, debug=True)


def main():
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
