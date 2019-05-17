# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from google.appengine.ext import ndb

from dashboard.api import api_request_handler
from dashboard.common import utils


class NudgeAlertHandler(api_request_handler.ApiRequestHandler):
  def _CheckUser(self):
    if not utils.IsValidSheriffUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    keys = self.request.get_all('key')
    start = self.request.get('new_start_revision')
    end = self.request.get('new_end_revision')
    try:
      start = int(start)
      end = int(end)
    except ValueError:
      return {'error': 'Invalid revisions %s, %s' % (start, end)}
    alerts = ndb.get_multi([ndb.Key(urlsafe=k) for k in keys])
    for a in alerts:
      a.start_revision = start
      a.end_revision = end
    ndb.put_multi(alerts)
    return {}
