# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Mocks out oauth2_decorator for unit testing."""

from apiclient import http
from dashboard import oauth2_decorator

HTTP_MOCK = http.HttpMock(headers={'status': '200'})


class MockOAuth2Decorator(object):
  """Mocks OAuth2Decorator for testing."""

  # This list will be used to keep a copy of the mocked http requests' bodies.
  # Note that this is a class variable because it may not be easy to get the
  # particular instance of the decorator used.
  past_bodies = []

  def __init__(self, client_id, client_secret, scope, message, callback_path):
    self.client_id = client_id
    self.client_secret = client_secret
    self.scope = scope
    self.message = message
    self.callback_path = callback_path

  def http(self):
    # The body attribute is set after this is returned, so all we can do here
    # is to save the previous one before it's overriden.
    MockOAuth2Decorator.past_bodies.append(HTTP_MOCK.body)
    return HTTP_MOCK

  def oauth_required(self, method):
    def check_oauth(request_handler, *args, **kwargs):
      resp = method(request_handler, *args, **kwargs)
      return resp
    return check_oauth


oauth2_decorator.decorator = MockOAuth2Decorator(
    client_id='client_id',
    client_secret='client_secret',
    scope='scope',
    message='message',
    callback_path='callback_path')
