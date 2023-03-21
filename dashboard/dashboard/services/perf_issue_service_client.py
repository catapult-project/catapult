# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# adding even we are running in python 3 to avoid pylint 2.7 complains.
from __future__ import absolute_import

import json

from dashboard.common import utils
from dashboard.services import request

if utils.IsStagingEnvironment():
  _SERVICE_URL = 'https://perf-issue-service-dot-chromeperf-stage.uc.r.appspot.com/'
else:
  _SERVICE_URL = 'https://perf-issue-service-dot-chromeperf.appspot.com/'

_ISSUES_PERFIX = 'issues/'


def GetIssues(**kwargs):
  url = _SERVICE_URL + _ISSUES_PERFIX
  try:
    resp = request.RequestJson(
        url, method='GET', use_cache=False, use_auth=True, **kwargs)
    return resp
  except request.RequestError as e:
    try:
      return json.loads(e.content)
    except ValueError:
      return {"error": str(e)}
