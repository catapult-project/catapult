#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from services import request


class Api(object):
  SERVICE_URL = 'https://chromeperf.appspot.com/api'

  def __init__(self, credentials):
    self._credentials = credentials

  def Request(self, endpoint, **kwargs):
    """Send a request to some dashboard service endpoint."""
    kwargs.setdefault('credentials', self._credentials)
    kwargs.setdefault('method', 'POST')
    return json.loads(request.Request(self.SERVICE_URL + endpoint, **kwargs))

  def Describe(self, test_suite):
    """Obtain information about a given test_suite.

    Args:
      test_suite: A string with the name of the test suite.

    Returns:
      A dict with information about: bots, caseTags, cases, and measurements.
    """
    return self.Request('/describe/%s' % test_suite)

  def ListTestPaths(self, test_suite, sheriff):
    """Lists test paths for the given test_suite.

    Args:
      test_suite: String with test suite to get paths for.
      sheriff: Include only test paths monitored by the given sheriff rotation,
          use 'all' to return all test paths regardless of rotation.

    Returns:
      A list of test paths. Ex. ['TestPath1', 'TestPath2']
    """
    return self.Request(
        '/list_timeseries/%s' % test_suite, params={'sheriff': sheriff})
