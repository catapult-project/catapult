# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Polls the sheriff_config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from dashboard.common.utils import GetEmail
from dashboard import sheriff_config_pb2
from dashboard.models.subscription import Subscription
import google.auth
from google.auth import jwt
from google.auth.transport.requests import AuthorizedSession
from google.protobuf import json_format


class InternalServerError(Exception):
  """An error indicating that something unexpected happens."""
  pass


def GetSheriffConfigClient():
  """Get a cached SheriffConfigClient instance.
  Most code should use this rather than constructing a SheriffConfigClient
  directly.
  """
  # pylint: disable=protected-access
  if not hasattr(GetSheriffConfigClient, '_client'):
    GetSheriffConfigClient._client = SheriffConfigClient()
  return GetSheriffConfigClient._client


class SheriffConfigClient(object):
  """Wrapping of sheriff-config HTTP API."""

  def __init__(self):
    """Make the Cloud Endpoints request from this handler."""
    credentials, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/userinfo.email'])
    jwt_credentials = jwt.Credentials.from_signing_credentials(
        credentials, 'sheriff-config-dot-chromeperf.appspot.com')
    self._session = AuthorizedSession(jwt_credentials)

  @staticmethod
  def _ParseSubscription(revision, subscription):
    return Subscription(
        revision=revision,
        name=subscription.name,
        rotation_url=subscription.rotation_url,
        notification_email=subscription.notification_email,
        bug_labels=list(subscription.bug_labels),
        bug_components=list(subscription.bug_components),
        bug_cc_emails=list(subscription.bug_cc_emails),
        visibility=subscription.visibility,
    )

  def Match(self, path, check=False):
    response = self._session.post(
        'https://sheriff-config-dot-chromeperf.appspot.com/subscriptions/match',
        json={'path': path})
    if response.status_code == 404: # If no subscription matched
      return [], None
    if not response.ok:
      err_msg = '%r\n%s' % (response, response.text)
      if check:
        raise InternalServerError(err_msg)
      return None, err_msg
    match_resp = json_format.Parse(response.text,
                                   sheriff_config_pb2.MatchResponse())
    return [self._ParseSubscription(s.revision, s.subscription)
            for s in match_resp.subscriptions], None

  def List(self, check=False):
    response = self._session.post(
        'https://sheriff-config-dot-chromeperf.appspot.com/subscriptions/list',
        json={'identity_email': GetEmail()})
    if not response.ok:
      err_msg = '%r\n%s' % (response, response.text)
      if check:
        raise InternalServerError(err_msg)
      return None, err_msg
    list_resp = json_format.Parse(response.text,
                                  sheriff_config_pb2.ListResponse())
    return [self._ParseSubscription(s.revision, s.subscription)
            for s in list_resp.subscriptions], None

  def Update(self, check=False):
    response = self._session.get(
        'https://sheriff-config-dot-chromeperf.appspot.com/configs/update')
    if response.ok:
      return True, None
    err_msg = '%r\n%s' % (response, response.text)
    if check:
      raise InternalServerError(err_msg)
    return False, err_msg
