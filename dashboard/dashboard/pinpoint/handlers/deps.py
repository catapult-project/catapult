# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from flask import make_response, request

from dashboard.common import cloud_metric
from dashboard.pinpoint.models.change import commit as commit_module
from dashboard.pinpoint.models.change import repository as repository_module

MISSING_PARAM_ERROR = 'Required parameters are invalid.'
DEPS_MALFORMATTED_ERROR = 'DEPS is malformatted.'


def _ToDict(deps):
  ret = {}
  if not deps:
    return ret
  for dep in deps:
    url, rev = dep[0], dep[1]
    ret[url] = rev
  ret = dict(sorted(ret.items()))
  return ret


@cloud_metric.APIMetric("pinpoint", "/api/deps")
def DepsHandlerGet():
  repository_url = request.args.get('repository_url', '')
  git_hash = request.args.get('git_hash', '')

  if repository_url == '' or git_hash == '':
    return make_response(json.dumps({'error': MISSING_PARAM_ERROR}), 400)

  try:
    repository = repository_module.RepositoryName(
        repository_url, add_if_missing=True)
  except AssertionError:
    # this just means that the repository already exists in DB.
    repository = repository_module.RepositoryName(repository_url)

  try:
    commit = commit_module.Commit(repository, git_hash)
    deps = commit.Deps()
  except NotImplementedError:
    # This means that the format of the requested DEPS is invalid.
    return make_response(json.dumps({'error': DEPS_MALFORMATTED_ERROR}), 400)

  # Convert to list and sort
  deps = _ToDict(deps)
  # This will return 200 with an empty dict if there is no DEPS for the
  # repository at the given revision.
  return make_response(json.dumps(deps), 200)
