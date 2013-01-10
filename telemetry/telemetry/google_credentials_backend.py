# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import form_based_credentials_backend

class GoogleCredentialsBackend(
    form_based_credentials_backend.FormBasedCredentialsBackend):
  @property
  def credentials_type(self):
    return 'google'

  @property
  def url(self):
    return 'https://accounts.google.com/'

  @property
  def login_form_id(self):
    return 'gaia_loginform'

  @property
  def already_logged_in_element_id(self):
    return 'gb'

  @property
  def login_input_id(self):
    return 'Email'

  @property
  def password_input_id(self):
    return 'Passwd'
