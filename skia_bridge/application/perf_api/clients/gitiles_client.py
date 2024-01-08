# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

import base64
import google_auth_httplib2
import google.auth
import json
import os
import six
import sys

from pathlib import Path
app_path = Path(__file__).parent.parent.parent
if str(app_path) not in sys.path:
  sys.path.insert(0, str(app_path))

from depot_tools import gclient_eval

from six.moves import http_client

GERRIT_SCOPE = 'https://www.googleapis.com/auth/gerritcodereview'

class RequestError(http_client.HTTPException):

  def __init__(self, msg, headers, content):
    super().__init__(msg)
    self.headers = headers
    self.content = content


class NotFoundError(RequestError):
  """Raised when a request gives a HTTP 404 error."""

class GitilesClient:

  def __init__(self, scope=None, timeout=60):
    credentials, _ = google.auth.default()
    if credentials.requires_scopes:
      scope = scope or GERRIT_SCOPE
      credentials = credentials.with_scopes([scope])

    http = google_auth_httplib2.AuthorizedHttp(credentials)
    http.timeout = timeout
    self._client = http

  def GetFileContent(self, repository_url, git_hash, path):
    """Fetches the contents of a file at a particular commit.

    Args:
      repository_url: The git url of the repository.
      git_hash: The git hash of the commit, or "HEAD".
      path: The path in the repository to the file.

    Returns:
      A string containing the file contents.

    Raises:
      NotFoundError: The repository, commit, or file was not found in Gitiles.
      http_client.HTTPException: A network or HTTP error occurred.
    """
    url = '%s/+/%s/%s?format=TEXT' % (repository_url, git_hash, path)

    response, content = self._client.request(url, method='GET')
    status = response.get('status')
    if status == '404':
      raise NotFoundError(
        'HTTP status code %s: %s' % (status, repr(content[0:200])),
        response, content)

    if not status.startswith('2'):
      raise RequestError(
        'Failure in request for `%s`; HTTP status code %s: %s' %
        (url, status, repr(content[0:200])), response, content)

    return six.ensure_str(base64.b64decode(content))

  def ParseGitDependencies(self, content, repository_url, git_hash):
    """Parses the git based dependencies from DEPS files.

    Args:
      content: The DEPS content, to be passed onto gclient_eval.Parse()

    Returns:
      A dict of repository url to git hash
    """
    try:
      deps_data = gclient_eval.Parse(
          content, '{}@{}/DEPS'.format(
              repository_url,
              git_hash,
          ))
    except gclient_eval.Error:
      return {}

    git_deps = {}
    for dep in deps_data.get('deps', {}).values():
      # The parser defaults to git dep_type.
      if dep.get('dep_type', '') != 'git':
        continue

      url = dep.get('url')
      parts = url.split('@')
      if len(parts) < 2:
        # The dependency is not pinned to a revision.
        continue
      if len(parts) > 2:
        raise NotImplementedError('Unknown DEP format: ' + url)

      url, git_hash = parts
      if url.endswith('.git'):
        url = url[:-4]
      git_deps[url] = git_hash

    return git_deps

  def GetGitDepsJSON(self, repository_url, git_hash):
    content = self.GetFileContent(repository_url, git_hash, 'DEPS')
    return self.ParseGitDependencies(content, repository_url, git_hash)


