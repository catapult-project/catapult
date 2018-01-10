# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.common import namespaced_stored_object


_BOTS_TO_DIMENSIONS = 'bot_dimensions_map'


class Config(webapp2.RequestHandler):
  """Handler returning site configuration details."""

  def get(self):
    # TODO: Merge bot_browser_map_2, bot_dimensions_map, and the builder map
    # into one mapping.
    bots_to_dimensions = namespaced_stored_object.Get(_BOTS_TO_DIMENSIONS)
    self.response.out.write(json.dumps({
        'configurations': sorted(bots_to_dimensions.iterkeys()),
    }))
