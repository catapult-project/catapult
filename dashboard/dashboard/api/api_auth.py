# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import functools
import logging

from google.appengine.api import oauth

from dashboard.common import datastore_hooks
from dashboard.common import utils


OAUTH_CLIENT_ID_WHITELIST = [
    # This oauth client id is from the 'chromeperf' API console.
    '62121018386-h08uiaftreu4dr3c4alh3l7mogskvb7i.apps.googleusercontent.com',
]
OAUTH_SCOPES = (
    'https://www.googleapis.com/auth/userinfo.email',
)


class ApiAuthException(Exception):
  pass


class OAuthError(ApiAuthException):
  def __init__(self):
    super(OAuthError, self).__init__('User authentication error')


class NotLoggedInError(ApiAuthException):
  def __init__(self):
    super(NotLoggedInError, self).__init__('User not authenticated')


class InternalOnlyError(ApiAuthException):
  def __init__(self):
    super(InternalOnlyError, self).__init__('User does not have access')


def _AuthorizeOauthUser():
  try:
    user = oauth.get_current_user(OAUTH_SCOPES)
    if user and not user.email().endswith('.gserviceaccount.com'):
      # For non-service account, need to verify that the OAuth client ID
      # is in our whitelist.
      client_id = oauth.get_client_id(OAUTH_SCOPES)
      if client_id not in OAUTH_CLIENT_ID_WHITELIST:
        logging.info('OAuth client id %s for user %s not in whitelist',
                     client_id, user.email())
        user = None
        raise OAuthError
  except oauth.Error:
    raise OAuthError

  if not user:
    raise NotLoggedInError

  logging.info('OAuth user logged in as: %s', user.email())
  if utils.IsGroupMember(user.email(), 'chromeperf-access'):
    datastore_hooks.SetPrivilegedRequest()


def Authorize(function_to_wrap):
  @functools.wraps(function_to_wrap)
  def Wrapper(*args, **kwargs):
    _AuthorizeOauthUser()

    return function_to_wrap(*args, **kwargs)
  return Wrapper
