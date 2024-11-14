# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Support python3
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
import six
import six.moves.urllib.parse

import google_auth_httplib2

_EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
_JSON_RESPONSE_PREFIX = b")]}'\n"


class AuthServiceClientError(Exception):
  """All errors associated with the LUCI Auth Service client module."""


class InvalidSetup(AuthServiceClientError):

  def __init__(self, message):
    super().__init__('invalid setup: {}'.format(message))


class MembershipCheckFailed(AuthServiceClientError):

  def __init__(self, message):
    super().__init__('membership check failed: {}'.format(message))


class LUCIAuthServiceClient:
  """Client for LUCI Auth Service."""

  def __init__(self, host_url, http=None, credentials=None, scope=_EMAIL_SCOPE):
    if not (http or credentials):
      raise InvalidSetup('need at least one of http or credentials')

    if credentials:
      if scope and credentials.requires_scopes:
        credentials = credentials.with_scopes([scope])
      http = google_auth_httplib2.AuthorizedHttp(credentials, http=http)

    self._host = host_url.strip().rstrip('/')
    self._http = http

  def CheckMembership(self, identity, group):
    """Queries Auth Service to check if the user is in the given group.

    Args:
      identity: the user email address to check.
      group: name of the group.

    Returns:
      True if user is a member, False otherwise.

    Raises:
      MembershipCheckFailed if the query failed.
    """
    # Construct the URL for the query.
    url = '{host}/auth/api/v1/memberships/check'.format(host=self._host)
    params = six.moves.urllib.parse.urlencode({
        'identity': 'user:{email}'.format(email=identity),
        'groups': group
    })
    query_url = '{endpoint}?{params}'.format(endpoint=url, params=params)

    response, content = self._http.request(query_url, method='GET')

    if not response['status'].startswith('2'):
      logging.error(
          'Failed to check membership of %s. '
          'Response headers: %s, body: %s', identity, response, content)
      raise MembershipCheckFailed('response status={}'.format(
          response['status']))

    content = six.ensure_binary(content)
    if content.startswith(_JSON_RESPONSE_PREFIX):
      content = content[len(_JSON_RESPONSE_PREFIX):]
    body = json.loads(content)

    is_member = body['is_member']
    return is_member
