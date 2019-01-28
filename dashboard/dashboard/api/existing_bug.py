# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard import associate_alerts
from dashboard.api import api_request_handler
from dashboard.common import utils


class ExistingBugHandler(api_request_handler.ApiRequestHandler):
  def _CheckUser(self):
    if not utils.IsValidSheriffUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    keys = self.request.get_all('key')
    bug_id = int(self.request.get('bug'))
    alerts = ndb.get_multi([ndb.Key(urlsafe=k) for k in keys])
    associate_alerts.AssociateAlerts(bug_id, alerts)
    return {}
