# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Polls the sheriff_config service."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from dashboard import sheriff_pb2
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
    return Sheriff(
        key=ndb.Key('Sheriff', subscription.name),
        url=subscription.rotation_url,
        email=subscription.notification_email,
        internal_only=(subscription.visibility !=
                       sheriff_pb2.Subscription.PUBLIC),
        # Sheriff model only support glob patterns
        patterns=[p.glob for p in subscription.patterns if p.glob],
        lables=(subscription.bug_labels +
                ['Component-' + c.replace('>', '-')
                 for c in subscription.bug_components]),
    )

  def Match(self, path):
    response = self._session.post(
        'https://sheriff-config-dot-chromeperf.appspot.com/subscriptions/match',
        json={'path': path})
    if not response.ok:
      return None, ('%r\n%s' % response, response.text)
    def Parse(s):
      subscription = json_format.Parse(s, sheriff_pb2.Subscription())
      return self._SubscriptionToSheriff(subscription)
    return [Parse(s) for s in response.json().get('subscriptions', [])], None

  def Update(self):
    response = self._session.get(
        'https://sheriff-config-dot-chromeperf.appspot.com/configs/update')
    if response.ok:
      return True, None
    return False, ('%r\n%s' % response, response.text)
