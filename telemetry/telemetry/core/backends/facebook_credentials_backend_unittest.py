# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core.backends import facebook_credentials_backend
from telemetry.core. \
    backends import form_based_credentials_backend_unittest_base


class TestFacebookCredentialsBackend(
    form_based_credentials_backend_unittest_base.
    FormBasedCredentialsBackendUnitTestBase):
  def setUp(self):
    self._credentials_type = 'facebook'

  def testLoginUsingMock(self):
    self._LoginUsingMock(
        facebook_credentials_backend.FacebookCredentialsBackend(),
        'http://www.facebook.com/', 'email', 'pass')
