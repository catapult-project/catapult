# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.api import api_request_handler
from dashboard.api import utils as api_utils
from dashboard.common import file_bug
from dashboard.common import utils


class NewBugHandler(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    if not utils.IsValidSheriffUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    owner = self.request.get('owner')
    cc = self.request.get('cc')
    summary = self.request.get('summary')
    description = self.request.get('description')
    project = self.request.get('project', 'chromium')
    labels = self.request.get_all('label')
    components = self.request.get_all('component')
    keys = self.request.get_all('key')
    bisect = api_utils.ParseBool(self.request.get('bisect', 'true'))
    http = utils.ServiceAccountHttp()

    return file_bug.FileBug(http, owner, cc, summary, description, project,
                            labels, components, keys, bisect)
