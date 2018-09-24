#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from services import request


class Api(object):
  SERVICE_URL = 'https://pinpoint-dot-chromeperf.appspot.com/api'

  def __init__(self, credentials):
    self._credentials = credentials

  @property
  def user_email(self):
    """Get the email address of the authenticated user."""
    return self._credentials.id_token['email']

  def Request(self, endpoint, **kwargs):
    """Send a request to some pinpoint endpoint."""
    kwargs.setdefault('credentials', self._credentials)
    return json.loads(request.Request(self.SERVICE_URL + endpoint, **kwargs))

  def Jobs(self):
    """List jobs for the authenticated user."""
    return self.Request('/jobs')

  def NewJob(self, **kwargs):
    """Create a new pinpoint job."""
    kwargs.setdefault('user', self.user_email)
    return self.Request('/new', method='POST', data=kwargs)
