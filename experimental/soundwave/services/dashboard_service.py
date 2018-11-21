#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Make requests to the Chrome Perf Dashboard API.

For more details on the API see:
https://chromium.googlesource.com/catapult.git/+/HEAD/dashboard/dashboard/api/README.md
"""

import json

from services import request

SERVICE_URL = 'https://chromeperf.appspot.com/api'


def Request(endpoint, **kwargs):
  """Send a request to some dashboard service endpoint."""
  kwargs.setdefault('use_auth', True)
  kwargs.setdefault('method', 'POST')
  return json.loads(request.Request(SERVICE_URL + endpoint, **kwargs))


def Describe(test_suite):
  """Obtain information about a given test_suite.

  Args:
    test_suite: A string with the name of the test suite.

  Returns:
    A dict with information about: bots, caseTags, cases, and measurements.
  """
  return Request('/describe', params={'test_suite': test_suite})


def Timeseries2(**kwargs):
  """Get timeseries data for a particular test path."""
  for col in ('test_suite', 'measurement', 'bot'):
    if col not in kwargs:
      raise TypeError('Missing required argument: %s' % col)
  try:
    return Request('/timeseries2', params=kwargs)
  except request.ClientError as exc:
    if exc.response.status == 404:
      raise KeyError('Timeseries not found')
    raise  # Re-raise the original exception.


def ListTestPaths(test_suite, sheriff):
  """Lists test paths for the given test_suite.

  Args:
    test_suite: String with test suite to get paths for.
    sheriff: Include only test paths monitored by the given sheriff rotation,
        use 'all' to return all test paths regardless of rotation.

  Returns:
    A list of test paths. Ex. ['TestPath1', 'TestPath2']
  """
  return Request(
      '/list_timeseries/%s' % test_suite, params={'sheriff': sheriff})
