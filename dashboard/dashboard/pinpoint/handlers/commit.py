# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.api import api_request_handler
from dashboard.pinpoint.models import change


class Commit(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    pass

  def Post(self):
    git_hash = self.request.get('git_hash')
    try:
      c = change.Commit.FromDict({
          'repository': 'chromium',
          'git_hash': git_hash,
      })
      return c.AsDict()
    except KeyError:
      raise api_request_handler.BadRequestError(
          'Unknown git hash: %s' % git_hash)
