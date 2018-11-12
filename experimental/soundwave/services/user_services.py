#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from services import chrome_perf_auth
from services import isolate_service


class UserServices(object):
  def __init__(self, flags):
    """Wrapper for access to APIs available to an authenticated user."""
    self._credentials = chrome_perf_auth.GetUserCredentials(flags)
    self._isolate = None

  @property
  def isolate(self):
    if self._isolate is None:
      self._isolate = isolate_service.Api(self._credentials)
    return self._isolate
