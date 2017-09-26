# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for interfacing with Gerrit, a web-based code review tool for Git.

API doc: https://gerrit-review.googlesource.com/Documentation/rest-api.html
"""

from dashboard.services import request


def GetChange(server_url, change_id, fields=None):
  url = '%s/changes/%s' % (server_url, change_id)
  return request.RequestJson(url, o=fields)
