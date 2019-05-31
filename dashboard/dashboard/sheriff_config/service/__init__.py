# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Support python3
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from flask import Flask, request, jsonify
from google.cloud import datastore
from google.protobuf import json_format
from flask_talisman import Talisman
import base64
import google.auth
import httplib2
import luci_config
import os
import sheriff_config_pb2
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
  _ = Talisman(app)

  environ = os.environ if test_config is None else test_config.get(
      'environ', {})

  # We can set up a preconfigured HTTP instance from the test_config, otherwise
  # we'll use the default auth for the production environment.
  if test_config:
    http = test_config.get('http')
  else:
    http = httplib2.Http()
    credentials = google.auth.default()
    http = credentials.authorize(http)

  # In the python37 environment, we need to synthesize the URL from the
  # various parts in the environment variable, because we do not have access
  # to the appengine APIs in the python37 standard environment.
  domain_parts = {
      'app_id': environ.get('GOOGLE_CLOUD_PROJECT', ''),
      'service': environ.get('GAE_SERVICE', ''),
  }
  empty_keys = [k for k, v in domain_parts.items() if len(v) == 0]
  if len(empty_keys):
    raise MissingEnvironmentVars(empty_keys)
  domain = '{parts[service]}-dot-{parts[app_id]}.appspot.com'.format(
      parts=domain_parts)

  # We create an instance of the luci-config client, which we'll use in all
  # requests handled in this application.
  config_client = luci_config.CreateConfigClient(http)

  # First we check whether the test_config already has a predefined
  # datastore_client.
  if test_config:
    datastore_client = test_config.get('datastore_client')
  else:
    datastore_client = datastore.Client()

  @app.route('/service-metadata')
  def ServiceMetadata():  # pylint: disable=unused-variable
    return jsonify({
        'version': '1.0',
        'validation': {
            'patterns': [{
                'config_set': 'regex:projects/.+',
                'path': 'regex:chromeperf-sheriff.cfg'
            }],
            'url': 'https://%s/configs/validate' % (domain)
        }
    })

  @app.route('/configs/validate', methods=['POST'])
  def Validate():  # pylint: disable=unused-variable
    validation_request = request.get_json()
    if validation_request is None:
      return u'Invalid request.', 400
    for member in ('config_set', 'path', 'content'):
      if member not in validation_request:
        return u'Missing \'%s\' member in request.' % (member), 400
    try:
      _ = validator.Validate(
          base64.standard_b64decode(validation_request['content']))
    except validator.Error as error:
      return jsonify({
          'messages': [{
              'path': validation_request['path'],
              'severity': 'ERROR',
              'text': '%s' % (error)
          }]
      })
    return jsonify({})

  @app.route('/configs/update')
  def UpdateConfigs():  # pylint: disable=unused-variable
    """Poll the luci-config service."""
    try:
      configs = luci_config.FindAllSheriffConfigs(config_client)
      luci_config.StoreConfigs(datastore_client, configs.get('configs', []))
      return jsonify({})
    except (luci_config.InvalidConfigError,
            luci_config.InvalidContentError) as error:
      app.logger.debug(error)
      return jsonify({}), 500

  @app.route('/subscriptions/match', methods=['POST'])
  def MatchSubscriptions():  # pylint: disable=unused-variable
    """Match the subscriptions given the request.

    This is an API handler, which requires that we have an authenticated user
    making the request. We'll require that the user either be a service account
    (from the main dashboard service) or an authenticated user. We'll enforce
    that we're only serving "public" Subscriptions to non-privileged users.
    """

    match_request = json_format.Parse(request.get_data(),
                                      sheriff_config_pb2.MatchRequest())
    match_response = sheriff_config_pb2.MatchResponse()
    for config_set, revision, subscription in luci_config.FindMatchingConfigs(
        datastore_client, match_request):
      subscription_metadata = match_response.subscriptions.add()
      subscription_metadata.config_set = config_set
      subscription_metadata.revision = revision
      subscription_metadata.subscription.CopyFrom(subscription)
    if not match_response.subscriptions:
      return jsonify({}), 404
    return (json_format.MessageToJson(
        match_response, preserving_proto_field_name=True), 200, {
            'Content-Type': 'application/json'
        })

  return app
