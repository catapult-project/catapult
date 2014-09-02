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
    backend = codepen_credentials_backend.CodePenCredentialsBackend()
    self._LoginUsingMock(backend, backend.url, backend.login_input_id,
                         backend.password_input_id, backend.login_form_id,
                         backend.logged_in_javascript)
