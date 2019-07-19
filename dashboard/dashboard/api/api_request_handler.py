# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import re
import traceback

import webapp2

from dashboard.api import api_auth
from dashboard.common import utils

_ALLOWED_ORIGINS = [
    'chromeperf.appspot.com',
    'pinpoint-dot-chromeperf.appspot.com',
    'chromiumdash.appspot.com',
    'chromiumdash-staging.googleplex.com',
]


class BadRequestError(Exception):
  pass


class ForbiddenError(Exception):
  def __init__(self):
    super(ForbiddenError, self).__init__('Access denied')


class NotFoundError(Exception):
  def __init__(self):
    super(NotFoundError, self).__init__('Not found')


class ApiRequestHandler(webapp2.RequestHandler):
  """API handler for api requests.

  Convenience methods handling authentication errors and surfacing them.
  """

  def _CheckUser(self):
    """Checks whether the user has permission to make requests.

    This method must be overridden by subclasses to perform access control.

    Raises:
      api_auth.NotLoggedInError: The user was not logged in,
          and must be to be to make this request.
      api_auth.OAuthError: The request was not a valid OAuth request,
          or the client ID was not in the whitelist.
      ForbiddenError: The user does not have permission to make this request.
    """
    raise NotImplementedError()

  def _CheckIsInternalUser(self):
    if utils.IsDevAppserver():
      return
    self._CheckIsLoggedIn()
    if not utils.IsInternalUser():
      raise ForbiddenError()

  def _CheckIsLoggedIn(self):
    if utils.IsDevAppserver():
      return
    api_auth.Authorize()

  def post(self, *args):
    """Returns alert data in response to API requests.

    Outputs:
      JSON results.
    """
    self._SetCorsHeadersIfAppropriate()

    try:
      self._CheckUser()
    except api_auth.NotLoggedInError as e:
      self.WriteErrorMessage(e.message, 401)
      return
    except api_auth.OAuthError as e:
      self.WriteErrorMessage(e.message, 403)
      return
    except ForbiddenError as e:
      self.WriteErrorMessage(e.message, 403)
      return
    # Allow oauth.Error to manifest as HTTP 500.

    try:
      results = self.Post(*args)
      self.response.out.write(json.dumps(results))
    except NotFoundError as e:
      self.WriteErrorMessage(e.message, 404)
    except (BadRequestError, KeyError, TypeError, ValueError) as e:
      self.WriteErrorMessage(e.message, 400)

  def options(self, *_):  # pylint: disable=invalid-name
    self._SetCorsHeadersIfAppropriate()

  def Post(self, *_):
    raise NotImplementedError()

  def _SetCorsHeadersIfAppropriate(self):
    self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
    set_cors_headers = False
    origin = self.request.headers.get('Origin', '')
    for allowed in _ALLOWED_ORIGINS:
      dev_pattern = re.compile(
          r'https://[A-Za-z0-9-]+-dot-' + re.escape(allowed))
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
    logging.error(traceback.format_exc())
    self.response.set_status(status)
    self.response.out.write(json.dumps({'error': message}))
