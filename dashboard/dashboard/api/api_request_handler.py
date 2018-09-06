# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import re

import webapp2

from dashboard.api import api_auth

_ALLOWED_ORIGINS = [
    'chromeperf.appspot.com',
    'chromiumdash.appspot.com',
    'chromiumdash-staging.googleplex.com',
]


class BadRequestError(Exception):
  pass


class NotFoundError(Exception):
  def __init__(self):
    super(NotFoundError, self).__init__('Not found')


class ApiRequestHandler(webapp2.RequestHandler):
  """API handler for api requests.

  Convenience methods handling authentication errors and surfacing them.
  """

  def _AllowAnonymous(self):
    return False

  def post(self, *args):
    """Returns alert data in response to API requests.

    Outputs:
      JSON results.
    """
    self._SetCorsHeadersIfAppropriate()
    try:
      api_auth.Authorize()
    except api_auth.NotLoggedInError as e:
      if not self._AllowAnonymous():
        self.WriteErrorMessage(e.message, 401)
        return
    except api_auth.OAuthError as e:
      self.WriteErrorMessage(e.message, 403)
      return
    # Allow oauth.Error to manifest as HTTP 500.

    try:
      results = self.AuthorizedPost(*args)
      self.response.out.write(json.dumps(results))
    except NotFoundError as e:
      self.WriteErrorMessage(e.message, 404)
    except BadRequestError as e:
      self.WriteErrorMessage(e.message, 400)

  def options(self, *_):  # pylint: disable=invalid-name
    self._SetCorsHeadersIfAppropriate()

  def AuthorizedPost(self, *_):
    raise NotImplementedError()

  def _SetCorsHeadersIfAppropriate(self):
    self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
    set_cors_headers = False
    origin = self.request.headers.get('Origin', '')
    for allowed in _ALLOWED_ORIGINS:
      dev_pattern = re.compile(
          r'https://[A-Za-z0-9]+-dot-' + re.escape(allowed))
      prod_pattern = re.compile(r'https://' + re.escape(allowed))
      if dev_pattern.match(origin) or prod_pattern.match(origin):
        set_cors_headers = True
    if not set_cors_headers:
      return
    self.response.headers.add_header('Access-Control-Allow-Origin', origin)
    self.response.headers.add_header('Access-Control-Allow-Credentials', 'true')
    self.response.headers.add_header(
        'Access-Control-Allow-Methods', 'GET,OPTIONS,POST')
    self.response.headers.add_header(
        'Access-Control-Allow-Headers', 'Accept,Authorization,Content-Type')
    self.response.headers.add_header('Access-Control-Max-Age', '3600')

  def WriteErrorMessage(self, message, status):
    logging.error('Error: %r', message)
    self.response.set_status(status)
    self.response.out.write(json.dumps({'error': message}))
