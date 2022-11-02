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
import six

from dashboard.api import api_auth
from dashboard.common import utils
from flask import make_response, request
if six.PY2:
  import webapp2

_ALLOWED_ORIGINS = [
    'chromeperf.appspot.com',
    'pinpoint-dot-chromeperf.appspot.com',
    'chromiumdash.appspot.com',
    'chromiumdash-staging.googleplex.com',
]
if utils.IsStagingEnvironment():
  _ALLOWED_ORIGINS = [
      'chromeperf-stage.uc.r.appspot.com',
      'pinpoint-dot-chromeperf-stage.uc.r.appspot.com',
  ]


class BadRequestError(Exception):
  pass


class ForbiddenError(Exception):

  def __init__(self):
    # TODO(https://crbug.com/1262292): Change to super() after Python2 trybots retire.
    # pylint: disable=super-with-arguments
    super(ForbiddenError, self).__init__('Access denied')


class NotFoundError(Exception):

  def __init__(self):
    # TODO(https://crbug.com/1262292): Change to super() after Python2 trybots retire.
    # pylint: disable=super-with-arguments
    super(NotFoundError, self).__init__('Not found')


def SafeOriginRegex(prefix, origin):
  return re.compile(r'^' + prefix + re.escape(origin) + '$')


def RequestHandlerDecoratorFactory(user_checker):

  def RequestHandlerDecorator(request_handler):

    def Wrapper():
      if request.method == 'OPTIONS':
        response = make_response()
        _SetCorsHeadersIfAppropriate(request, response)
        return response

      try:
        user_checker()
      except api_auth.NotLoggedInError as e:
        return _WriteErrorMessage(str(e), 401)
      except api_auth.OAuthError as e:
        return _WriteErrorMessage(str(e), 403)
      except ForbiddenError as e:
        return _WriteErrorMessage(str(e), 403)
      # Allow oauth.Error to manifest as HTTP 500.

      try:
        results = request_handler()
      except NotFoundError as e:
        return _WriteErrorMessage(str(e), 404)
      except (BadRequestError, KeyError, TypeError, ValueError) as e:
        return _WriteErrorMessage(str(e), 400)
      except ForbiddenError as e:
        return _WriteErrorMessage(str(e), 403)

      response = make_response(json.dumps(results))
      _SetCorsHeadersIfAppropriate(request, response)
      return response

    Wrapper.__name__ = request_handler.__name__
    return Wrapper

  return RequestHandlerDecorator


def _SetCorsHeadersIfAppropriate(req, resp):
  resp.headers['Content-Type'] = 'application/json; charset=utf-8'
  set_cors_headers = False
  origin = req.headers.get('Origin', '')
  for allowed in _ALLOWED_ORIGINS:
    dev_pattern = SafeOriginRegex(r'https://[A-Za-z0-9-]+-dot-', allowed)
    prod_pattern = SafeOriginRegex(r'https://', allowed)
    if dev_pattern.match(origin) or prod_pattern.match(origin):
      set_cors_headers = True
  if set_cors_headers:
    resp.headers['Access-Control-Allow-Origin'] = origin
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS,POST'
    resp.headers[
        'Access-Control-Allow-Headers'] = 'Accept,Authorization,Content-Type'
    resp.headers['Access-Control-Max-Age'] = '3600'


def _WriteErrorMessage(message, status):
  logging.error(traceback.format_exc())
  return make_response(json.dumps({'error': message}), status)


if six.PY2:

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
            or the client ID was not in the allowlist.
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
      self._Respond(self.Post, *args)

    def get(self, *args):
      self._Respond(self.Get, *args)

    def _Respond(self, cb, *args):
      self._SetCorsHeadersIfAppropriate()

      try:
        self._CheckUser()
      except api_auth.NotLoggedInError as e:
        self.WriteErrorMessage(str(e), 401)
        return
      except api_auth.OAuthError as e:
        self.WriteErrorMessage(str(e), 403)
        return
      except ForbiddenError as e:
        self.WriteErrorMessage(str(e), 403)
        return
      # Allow oauth.Error to manifest as HTTP 500.

      try:
        results = cb(*args)
        self.response.out.write(json.dumps(results))
      except NotFoundError as e:
        self.WriteErrorMessage(str(e), 404)
      except (BadRequestError, KeyError, TypeError, ValueError) as e:
        self.WriteErrorMessage(str(e), 400)
      except ForbiddenError as e:
        self.WriteErrorMessage(str(e), 403)

    def options(self, *_):  # pylint: disable=invalid-name
      self._SetCorsHeadersIfAppropriate()

    def Get(self, *_):
      raise NotImplementedError()

    def Post(self, *args, **kwargs):
      del args, kwargs  # Unused.
      raise NotImplementedError()

    def _SetCorsHeadersIfAppropriate(self):
      self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
      set_cors_headers = False
      origin = self.request.headers.get('Origin', '')
      for allowed in _ALLOWED_ORIGINS:
        dev_pattern = SafeOriginRegex(r'https://[A-Za-z0-9-]+-dot-', allowed)
        prod_pattern = SafeOriginRegex(r'https://', allowed)
        if dev_pattern.match(origin) or prod_pattern.match(origin):
          set_cors_headers = True
      if not set_cors_headers:
        return
      self.response.headers.add_header('Access-Control-Allow-Origin', origin)
      self.response.headers.add_header('Access-Control-Allow-Credentials',
                                       'true')
      self.response.headers.add_header('Access-Control-Allow-Methods',
                                       'GET,OPTIONS,POST')
      self.response.headers.add_header('Access-Control-Allow-Headers',
                                       'Accept,Authorization,Content-Type')
      self.response.headers.add_header('Access-Control-Max-Age', '3600')

    def WriteErrorMessage(self, message, status):
      logging.error(traceback.format_exc())
      self.response.set_status(status)
      self.response.out.write(json.dumps({'error': message}))
