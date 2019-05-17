# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard import pinpoint_request
from dashboard.api import api_request_handler
from dashboard.common import descriptor
from dashboard.common import utils


# This is just like PinpointNewBisectRequestHandler (/pinpoint/new/bisect),
# except 1. this is dispatched for /api/new_pinpoint, so utils.GetEmail() uses
# OAuth instead of cookies, and 2. this accepts a Descriptor instead of a test
# path.
class NewPinpointHandler(api_request_handler.ApiRequestHandler):
  def _CheckUser(self):
    if not utils.IsValidSheriffUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    params = dict((a, self.request.get(a)) for a in self.request.arguments())
    desc = descriptor.Descriptor(
        params['suite'], params['measurement'], params['bot'],
        params.get('case'), params.get('statistic'))
    params['test_path'] = list(desc.ToTestPathsSync())[0]
    # TODO Find the first test_path that exists, maybe strip statistic.
    params['story_filter'] = params.get('case')
    return pinpoint_request.NewPinpointBisect(params)
