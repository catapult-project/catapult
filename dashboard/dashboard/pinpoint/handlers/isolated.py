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
from dashboard.pinpoint.models import isolated


# TODO: Use Cloud Endpoints to make a proper API with a proper response.
class IsolatedHandler(webapp2.RequestHandler):
  """Handler for managing isolateds.

  A post request adds new isolated information.
  A get request looks up an isolated hash from the builder, commit, and target.
  """

  def get(self, builder_name, git_hash, target):
    try:
      isolated_hash = isolated.Get(builder_name, git_hash, target)
    except KeyError as e:
      self.response.set_status(404)
      self.response.write(e)
      return

    self.response.write(isolated_hash)

  def post(self):
    """Add new isolated information.

    Args:
      builder_name: The name of the builder that produced the isolated.
      git_hash: The git hash of the commit the isolated is for. If the isolated
          is for a DEPS roll, it's the git hash of the commit inside the roll.
      isolated_map: A JSON dict mapping the target names to the isolated hashes.
    """
    # Check permissions.
    if self.request.remote_addr not in utils.GetIpWhitelist():
      self.response.set_status(403)
      self.response.write('Permission denied')
      return

    # Get parameters.
    for parameter in ('builder_name', 'git_hash', 'isolated_map'):
      if parameter not in self.request.POST:
        self.response.set_status(400)
        self.response.write('Missing parameter: %s' % parameter)
        return

      if not self.request.get(parameter):
        self.response.set_status(400)
        self.response.write('Empty parameter: %s' % parameter)
        return

    builder_name = self.request.get('builder_name')
    git_hash = self.request.get('git_hash')
    isolated_map = self.request.get('isolated_map')

    # Validate parameters.
    try:
      isolated_map = json.loads(isolated_map)
    except ValueError:
      self.response.set_status(400)
      self.response.write('isolated_map is not valid JSON: %s' % isolated_map)
      return

    # Put information into the datastore.
    isolated_infos = {(builder_name, git_hash, target, isolated_hash)
                      for target, isolated_hash in isolated_map.iteritems()}
    isolated.Put(isolated_infos)
