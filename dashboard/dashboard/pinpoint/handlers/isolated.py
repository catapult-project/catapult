# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Service for tracking .isolateds and looking them up by builder and commit.

An .isolated file is a way to describe the dependencies of a specific build.

More about isolates:
https://github.com/luci/luci-py/blob/master/appengine/isolate/doc/client/Design.md
"""

import json

import webapp2

from dashboard.common import utils
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import isolated


# TODO: Use Cloud Endpoints to make a proper API with a proper response.
class Isolated(webapp2.RequestHandler):
  """Handler for managing isolateds.

  A post request adds new isolated information.
  A get request looks up an isolated hash from the builder, commit, and target.
  """

  def get(self):
    """Look up an isolated hash.

    Args:
      builder_name: The name of the builder that produced the isolated.
      change: The Change the isolated is for, as a JSON string.
      target: The isolated target.
    """
    # Get parameters.
    parameters = (
        ('builder_name', str),
        ('change', lambda x: change_module.Change.FromDict(json.loads(x))),
        ('target', str),
    )
    try:
      # pylint: disable=unbalanced-tuple-unpacking
      builder_name, change, target = self._ValidateParameters(parameters)
    except (KeyError, TypeError, ValueError) as e:
      self.response.set_status(400)
      self.response.write(e)
      return

    # Get.
    try:
      isolated_hash = isolated.Get(builder_name, change, target)
    except KeyError as e:
      self.response.set_status(404)
      self.response.write(e)
      return

    self.response.write(isolated_hash)

  def post(self):
    """Add new isolated information.

    Args:
      builder_name: The name of the builder that produced the isolated.
      change: The Change the isolated is for, as a JSON string.
      isolated_map: A JSON dict mapping the target names to the isolated hashes.
    """
    # Check permissions.
    if self.request.remote_addr not in utils.GetIpWhitelist():
      self.response.set_status(403)
      self.response.write('Permission denied')
      return

    # Get parameters.
    parameters = (
        ('builder_name', str),
        ('change', lambda x: change_module.Change.FromDict(json.loads(x))),
        ('isolated_map', json.loads),
    )
    try:
      # pylint: disable=unbalanced-tuple-unpacking
      builder_name, change, isolated_map = self._ValidateParameters(parameters)
    except (KeyError, TypeError, ValueError) as e:
      self.response.set_status(400)
      self.response.write(e)
      return

    # Put information into the datastore.
    isolated_infos = {(builder_name, change, target, isolated_hash)
                      for target, isolated_hash in isolated_map.iteritems()}
    isolated.Put(isolated_infos)

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
    parameter_names = tuple(parameter_name for parameter_name, _ in parameters)
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
