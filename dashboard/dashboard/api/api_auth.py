# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api import oauth

from dashboard.common import datastore_hooks
from dashboard.common import utils


OAUTH_CLIENT_ID_WHITELIST = [
    # This oauth client id is from Pinpoint.
    '62121018386-aqdfougp0ddn93knqj6g79vvn42ajmrg.apps.googleusercontent.com',
    # This oauth client id is from the 'chromeperf' API console.
    '62121018386-h08uiaftreu4dr3c4alh3l7mogskvb7i.apps.googleusercontent.com',
    # This oauth client id is from chromiumdash-staging.
    '377415874083-slpqb5ur4h9sdfk8anlq4qct9imivnmt.apps.googleusercontent.com',
    # This oauth client id is from chromiumdash.
    '975044924533-p122oecs8h6eibv5j5a8fmj82b0ct0nk.apps.googleusercontent.com',
    # This oauth client id is used to upload histograms from the perf waterfall.
    '113172445342431053212',
    'chromeperf@webrtc-perf-test.google.com.iam.gserviceaccount.com',
    # This oauth client id is used to upload histograms when debugging Fuchsia
    # locally (e.g. in a cron-job).
    'catapult-uploader@fuchsia-infra.iam.gserviceaccount.com',
    # This oauth client id is used to upload histograms from Fuchsia dev
    # builders.
    'garnet-ci-builder-dev@fuchsia-infra.iam.gserviceaccount.com',
    # This oauth client id is used from Fuchsia Garnet builders.
    'garnet-ci-builder@fuchsia-infra.iam.gserviceaccount.com',
    # These are more fuschia builders.
    'peridot-ci-builder@fuchsia-infra.iam.gserviceaccount.com',
    'topaz-ci-builder@fuchsia-infra.iam.gserviceaccount.com',
    'vendor-google-ci-builder@fuchsia-infra.iam.gserviceaccount.com',
    # This oauth client id used to upload histograms from cronet bots.
    '113172445342431053212',
    # Used by luci builders to upload perf data.
    'chrome-ci-builder@chops-service-accounts.iam.gserviceaccount.com',
]


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


def Authorize():
  try:
    email = utils.GetEmail()
  except oauth.OAuthRequestError:
    raise OAuthError

  if not email:
    raise NotLoggedInError

  try:
    if not email.endswith('.gserviceaccount.com'):
      # For non-service account, need to verify that the OAuth client ID
      # is in our whitelist.
      client_id = oauth.get_client_id(utils.OAUTH_SCOPES)
      if client_id not in OAUTH_CLIENT_ID_WHITELIST:
        logging.error('OAuth client id %s for user %s not in whitelist',
                      client_id, email)
        email = None
        raise OAuthError
  except oauth.OAuthRequestError:
    # Transient errors when checking the token result should result in HTTP 500,
    # so catch oauth.OAuthRequestError here, not oauth.Error (which would catch
    # both fatal and transient errors).
    raise OAuthError

  logging.info('OAuth user logged in as: %s', email)
  if utils.IsInternalUser():
    datastore_hooks.SetPrivilegedRequest()
