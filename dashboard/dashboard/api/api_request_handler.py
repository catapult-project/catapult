# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from dashboard.api import api_auth
from dashboard.common import request_handler


class BadRequestError(Exception):
  pass


class ApiRequestHandler(request_handler.RequestHandler):
  """API handler for api requests.

  Convenience methods handling authentication errors and surfacing them.
  """

  def post(self, *args):
    """Returns alert data in response to API requests.

    Outputs:
      JSON results.
    """
    try:
      results = self._TryAuthorizePost(*args)
      self.response.out.write(json.dumps(results))
    except BadRequestError as e:
      self.WriteErrorMessage(e.message, 400)
    except api_auth.NotLoggedInError:
      self.WriteErrorMessage('User not authenticated', 403)
    except api_auth.OAuthError:
      self.WriteErrorMessage('User authentication error', 403)

  @api_auth.Authorize
  def _TryAuthorizePost(self, *args):
    return self.AuthorizedPost(*args)

  def AuthorizedPost(self, *_):
    raise BadRequestError('Override this')

  def WriteErrorMessage(self, message, status):
    logging.error(message)
    self.response.set_status(status)
    self.response.out.write(json.dumps({'error': message}))
