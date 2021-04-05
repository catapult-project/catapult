# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Service for tracking CAS reference from RBE and looking them up by
builder and commit.

RBE is the Remote Build Execution used for building and storing the result
in Content Addressable Storage (CAS).
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json

from dashboard.api import api_request_handler
from dashboard.common import utils
from dashboard.pinpoint.models import cas
from dashboard.pinpoint.models import change as change_module


class CASReference(api_request_handler.ApiRequestHandler):
  """Handler for managing RBE-CAS references.

  A post request adds new CAS information.
  A get request looks up an CAS digest from the builder, commit, and target.
  """

  def get(self):
    """Look up a RBE-CAS digest.

    Args:
      builder_name: The name of the builder that produced the CAS.
      change: The Change the CAS is for, as a JSON string.
      target: The CAS target.
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
      cas_instance, cas_digest = cas.Get(builder_name, change, target)
    except KeyError as e:
      self.response.set_status(404)
      self.response.write(e)
      return

    self.response.write(
        json.dumps({
            'cas_instance': cas_instance,
            'cas_digest': cas_digest,
        }))

  def _CheckUser(self):
    # TODO: Remove when all Pinpoint builders are migrated to LUCI.
    if self.request.remote_addr in utils.GetIpAllowlist():
      return
    self._CheckIsInternalUser()

  def Post(self):
    """Add new RBE-CAS information.

    Args:
      builder_name: The name of the builder that produced the CAS.
      change: The Change the CAS is for, as a JSON string.
      cas_instance: The hostname of the server where the CAS are stored.
      cas_map: A JSON dict mapping the target names to the CAS digests.
    """
    # Get parameters.
    parameters = (
        ('builder_name', str),
        ('change', lambda x: change_module.Change.FromDict(json.loads(x))),
        ('cas_instance', str),
        ('cas_map', json.loads),
    )
    try:
      # pylint: disable=unbalanced-tuple-unpacking
      builder_name, change, cas_instance, cas_map = (
          self._ValidateParameters(parameters))
    except (KeyError, TypeError, ValueError) as e:
      self.response.set_status(400)
      self.response.write(json.dumps({'error': e.message}))
      return

    # Put information into the datastore.
    cas_references = [(builder_name, change, target, cas_instance,
                       cas_digest)
                      for target, cas_digest in cas_map.items()]
    cas.Put(cas_references)

    # Respond to the API user.
    self.response.write(json.dumps(cas_references))

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

