# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Service for tracking isolates and looking them up by builder and commit.

An isolate is a way to describe the dependencies of a specific build.

More about isolates:
https://github.com/luci/luci-py/blob/master/appengine/isolate/doc/client/Design.md
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.api import api_request_handler
from dashboard.api import api_auth
from dashboard.common import utils
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import isolate

if utils.IsRunningFlask():
  from flask import make_response, request
else:
  import webapp2

import logging

if utils.IsRunningFlask():

  def _CheckUser():
    if request.remote_addr and request.remote_addr in utils.GetIpAllowlist():
      return
    if utils.IsDevAppserver():
      return
    api_auth.Authorize()
    if not utils.IsInternalUser():
      raise api_request_handler.ForbiddenError()

  def _ValidateParameters(parameters, validators):
    """Ensure the right parameters are present and valid.
    Args:
      parameters: parameters in dictionary
      validators: Iterable of (name, converter) tuples where name is the
                  parameter name and converter is a function used to validate
                  and convert that parameter into its internal representation.
    Returns:
      A list of parsed parameter values.

    Raises:
      TypeError: The wrong parameters are present.
      ValueError: The parameters have invalid values.
    """
    given_parameters = set(parameters.keys())
    expected_parameters = set(validators.keys())

    if given_parameters != expected_parameters:
      logging.info('Unexpected request parameters. Given: %s. Expected: %s',
                   given_parameters, expected_parameters)
      if given_parameters - expected_parameters:
        raise TypeError('Unknown parameter: %s' % given_parameters -
                        expected_parameters)
      if expected_parameters - given_parameters:
        raise TypeError('Missing parameter: %s' % expected_parameters -
                        given_parameters)

    parameter_values = {}

    for parameter_name, parameter_value in parameters.items():
      converted_value = validators[parameter_name](parameter_value)
      if not converted_value:
        raise ValueError('Empty parameter: %s' % parameter_name)
      parameter_values[parameter_name] = converted_value

    return parameter_values

  @api_request_handler.RequestHandlerDecoratorFactory(_CheckUser)
  def IsolateHandler():
    if request.method == 'POST':
      validators = {
          'builder_name': str,
          'change': (lambda x: change_module.Change.FromDict(json.loads(x))),
          'isolate_server': str,
          'isolate_map': json.loads
      }
      validated_parameters = _ValidateParameters(request.form, validators)

      # Put information into the datastore.
      isolate_infos = [
          (validated_parameters['builder_name'], validated_parameters['change'],
           target, validated_parameters['isolate_server'], isolate_hash) for
          target, isolate_hash in validated_parameters['isolate_map'].items()
      ]

      isolate.Put(isolate_infos)

      return isolate_infos

    if request.method == 'GET':
      validators = {
          'builder_name': str,
          'change': (lambda x: change_module.Change.FromDict(json.loads(x))),
          'target': str
      }
      try:
        validated_parameters = _ValidateParameters(request.form, validators)
      except (KeyError, TypeError, ValueError) as e:
        return make_response(json.dumps({'error': str(e)}), 400)

      try:
        isolate_server, isolate_hash = isolate.Get(
            validated_parameters['builder_name'],
            validated_parameters['change'], validated_parameters['target'])
      except KeyError as e:
        return make_response(json.dumps({'error': str(e)}), 404)

      return {'isolate_server': isolate_server, 'isolate_hash': isolate_hash}
    return {}
else:
  class Isolate(api_request_handler.ApiRequestHandler):
    # pylint: disable=abstract-method
    """Handler for managing isolates.

    A post request adds new isolate information.
    A get request looks up an isolate hash from the builder, commit, and target.
    """

    def get(self, *_):
      """Look up an isolate hash.

      Args:
        builder_name: The name of the builder that produced the isolate.
        change: The Change the isolate is for, as a JSON string.
        target: The isolate target.
      """
      # Get parameters.
      parameters = (
          ('builder_name', str),
          ('change', lambda x: change_module.Change.FromDict(json.loads(x))),
          ('target', str),
      )
      logging.info('Received api/isolate GET request. Request.remote_addr: %s',
                   self.request.remote_addr)
      try:
        # pylint: disable=unbalanced-tuple-unpacking
        builder_name, change, target = self._ValidateParameters(parameters)
      except (KeyError, TypeError, ValueError) as e:
        self.response.set_status(400)
        self.response.write(e)
        return

      # Get.
      try:
        isolate_server, isolate_hash = isolate.Get(builder_name, change, target)
      except KeyError as e:
        self.response.set_status(404)
        self.response.write(e)
        return

      self.response.write(
          json.dumps({
              'isolate_server': isolate_server,
              'isolate_hash': isolate_hash,
          }))

    def _CheckUser(self):
      # TODO: Remove when all Pinpoint builders are migrated to LUCI.
      if self.request.remote_addr in utils.GetIpAllowlist():
        return
      self._CheckIsInternalUser()

    def Post(self, *args, **kwargs):
      """Add new isolate information.

      Args:
        builder_name: The name of the builder that produced the isolate.
        change: The Change the isolate is for, as a JSON string.
        isolate_server: The hostname of the server where the isolates are stored
        isolate_map: A JSON dict mapping the target names to the isolate hashes.
      """
      del args, kwargs  # Unused.
      # Get parameters.
      parameters = (
          ('builder_name', str),
          ('change', lambda x: change_module.Change.FromDict(json.loads(x))),
          ('isolate_server', str),
          ('isolate_map', json.loads),
      )
      try:
        # pylint: disable=unbalanced-tuple-unpacking
        builder_name, change, isolate_server, isolate_map = (
            self._ValidateParameters(parameters))
      except (KeyError, TypeError, ValueError) as e:
        self.response.set_status(400)
        self.response.write(json.dumps({'error': str(e)}))
        return

      # Put information into the datastore.
      isolate_infos = [(builder_name, change, target, isolate_server,
                        isolate_hash)
                       for target, isolate_hash in isolate_map.items()]
      isolate.Put(isolate_infos)

      # Respond to the API user.
      self.response.write(json.dumps(isolate_infos))

    def _ValidateParameters(self, parameters):
      """Ensure the right parameters are present and valid.

      Args:
        parameters: Iterable of (name, converter) tuples where name is the
                    parameter name and converter is a function used to validate
                    and convert that parameter into its internal representation.

      Returns:
        A list of parsed parameter values.

      Raises:
        TypeError: The wrong parameters are present.
        ValueError: The parameters have invalid values.
      """
      parameter_names = tuple(
          parameter_name for parameter_name, _ in parameters)
      for given_parameter in self.request.params:
        if given_parameter not in parameter_names:
          raise TypeError('Unknown parameter: %s' % given_parameter)

      parameter_values = []

      for parameter_name, parameter_converter in parameters:
        if parameter_name not in self.request.params:
          raise TypeError('Missing parameter: %s' % parameter_name)

        parameter_value = self.request.get(parameter_name)
        if not parameter_value:
          raise ValueError('Empty parameter: %s' % parameter_name)

        parameter_value = parameter_converter(parameter_value)

        parameter_values.append(parameter_value)

      return parameter_values


if utils.IsRunningFlask():

  def IsolateCleanupHandler():
    isolate.DeleteExpiredIsolates()
    return make_response('', 200)
else:

  class IsolateCleanup(webapp2.RequestHandler):

    def get(self):
      isolate.DeleteExpiredIsolates()
