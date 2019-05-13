# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Support python3
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os

from flask import Flask, request, jsonify
import validator


class Error(Exception):
  """Base class for service-related set-up errors."""


class MissingEnvironmentVars(Error):

  def __init__(self, env_vars):
    self.env_vars = env_vars
    super(MissingEnvironmentVars, self).__init__()

  def __str__(self):
    return 'Missing environment variables: %r' % (self.env_vars)


def CreateApp(test_config=None):
  """Factory for Flask App configuration.

  This is the factory function for setting up the service. This function
  contains all the HTTP routing information and handlers that are registered for
  the Flask application.

  Args:
    test_config: a dict of overrides for the app configuration.

  Raises:
    MissingEnvironmentVars: raised we find that we don't have the AppEngine
    environment variables available when creating the application.

  Returns:
    A Flask application configured with the appropriate URL handlers.
  """
  app = Flask(__name__, instance_relative_config=True)

  environ = os.environ if test_config is None else test_config.get(
      'environ', {})

  # In the python37 environment, we need to synthesize the URL from the
  # various parts in the environment variable, because we do not have access
  # to the appengine APIs in the python37 standard environment.
  domain_parts = {
      'app_id': environ.get('GAE_APPLICATION', ''),
      'service': environ.get('GAE_SERVICE', ''),
  }
  empty_keys = [k for k, v in domain_parts.items() if len(v) == 0]
  if len(empty_keys):
    raise MissingEnvironmentVars(empty_keys)
  domain = '{parts[service]}-dot-{parts[app_id]}.appspot.com'.format(
      parts=domain_parts)

  @app.route('/validate', methods=['POST'])
  def Validate():  # pylint: disable=unused-variable
    validation_request = request.get_json()
    if validation_request is None:
      return u'Invalid request.', 400
    for member in ('config_set', 'path', 'content'):
      if member not in validation_request:
        return u'Missing \'%s\' member in request.' % (member), 400
    try:
      _ = validator.Validate(validation_request['content'])
    except validator.Error as error:
      return jsonify({
          'messages': [{
              'path': validation_request['path'],
              'severity': 'ERROR',
              'text': '%s' % (error)
          }]
      })
    return jsonify({})

  @app.route('/service-metadata')
  def ServiceMetadata():  # pylint: disable=unused-variable
    return jsonify({
        'version': '1.0',
        'validation': {
            'patterns': [{
                'config_set': 'regex:projects/.+',
                'path': 'regex:chromeperf-sheriff.cfg'
            }],
            'url': 'https://%s/validate' % (domain)
        }
    })

  return app
