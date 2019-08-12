# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions for getting commit information from Pinpoint."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.common import datastore_hooks
from dashboard.services import request

_PINPOINT_URL = 'https://pinpoint-dot-chromeperf.appspot.com'


def NewJob(params):
  """Submits a new job request to Pinpoint."""
  return _Request(_PINPOINT_URL + '/api/new', params)


def _Request(endpoint, params):
  """Sends a request to an endpoint and returns JSON data."""
  assert datastore_hooks.IsUnalteredQueryPermitted()

  try:
    return request.RequestJson(
        endpoint, method='POST', use_cache=False, use_auth=True, **params)
  except request.RequestError as e:
    return json.loads(e.content)
