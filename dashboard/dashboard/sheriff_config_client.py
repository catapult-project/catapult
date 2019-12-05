# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Polls the sheriff_config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from dashboard import sheriff_pb2
from dashboard import sheriff_config_pb2
from dashboard.models.sheriff import Sheriff
from google.appengine.ext import ndb
import google.auth
from google.auth import jwt
from google.auth.transport.requests import AuthorizedSession
from google.protobuf import json_format


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
  def _SubscriptionToSheriff(subscription):
    sheriff = Sheriff(
        key=ndb.Key('Sheriff', subscription.name),
        internal_only=(subscription.visibility !=
                       sheriff_pb2.Subscription.PUBLIC),
        # Sheriff model only support glob patterns
        patterns=[p.glob for p in subscription.patterns if p.glob],
        labels=(list(subscription.bug_labels) +
                ['Component-' + c.replace('>', '-')
                 for c in subscription.bug_components]),
    )
    if subscription.rotation_url:
      sheriff.url = subscription.rotation_url
    if subscription.notification_email:
      sheriff.email = subscription.notification_email
    return sheriff

  def Match(self, path):
    response = self._session.post(
        'https://sheriff-config-dot-chromeperf.appspot.com/subscriptions/match',
        json={'path': path})
    if not response.ok:
      return None, ('%r\n%s' % response, response.text)
    match = json_format.Parse(response.text, sheriff_config_pb2.MatchResponse())
    return [self._SubscriptionToSheriff(s.subscription)
            for s in match.subscriptions], None

  def Update(self):
    response = self._session.get(
        'https://sheriff-config-dot-chromeperf.appspot.com/configs/update')
    if response.ok:
      return True, None
    return False, ('%r\n%s' % response, response.text)
