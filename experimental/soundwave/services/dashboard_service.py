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
    return self.Request('/describe', params={'test_suite': test_suite})
