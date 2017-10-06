# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.pinpoint.models.change import repository
from dashboard.services import gitiles_service


# TODO: Remove this module. Cache commit git details in the Datastore and
# include them in Commit.AsDict().
class Gitiles(webapp2.RequestHandler):
  """Handler that exposes gitiles service to UI."""

  def get(self):
    repo = self.request.get('repository')
    git_hash_1 = self.request.get('git_hash', self.request.get('git_hash_1'))
    git_hash_2 = self.request.get('git_hash_2')

    try:
      repository_url = repository.RepositoryUrl(repo)
    except KeyError:
      self.response.out.write(json.dumps(
          {'error': 'Unknown repository: %s' % repo}))
      return

    if not git_hash_1:
      self.response.out.write(json.dumps(
          {'error': "No 'git_hash' parameter specified."}))
      return

    if git_hash_2:
      result = gitiles_service.CommitRange(repo, git_hash_1, git_hash_2)
      self.response.out.write(json.dumps(result))
      return

    result = gitiles_service.CommitInfo(repository_url, git_hash_1)
    self.response.out.write(json.dumps(result))
