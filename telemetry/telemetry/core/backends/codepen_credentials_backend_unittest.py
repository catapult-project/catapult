# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core.backends import form_based_credentials_backend_unittest_base
from telemetry.core.backends import codepen_credentials_backend


class TestCodePenCredentialsBackend(
    form_based_credentials_backend_unittest_base.
    FormBasedCredentialsBackendUnitTestBase):
  def setUp(self):
    self._credentials_type = 'codepen'

  def testLoginUsingMock(self):
    self._LoginUsingMock(
        codepen_credentials_backend.CodePenCredentialsBackend(),
        'https://codepen.io/login', 'login-email-field', 'login-password',
        'login-login-form', 'document.querySelector(".login-area") === null')
