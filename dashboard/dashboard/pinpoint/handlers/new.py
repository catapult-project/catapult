# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.api import api_auth
from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import quest_generator as quest_generator_module


_ERROR_BUG_ID = 'Bug ID must be an integer.'


class New(webapp2.RequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def post(self):
    try:
      self._CreateJob()
    except (api_auth.ApiAuthException, KeyError, TypeError, ValueError) as e:
      self._WriteErrorMessage(e.message)

  def _WriteErrorMessage(self, message):
    self.response.out.write(json.dumps({'error': message}))

  @api_auth.Authorize
  def _CreateJob(self):
    """Start a new Pinpoint job."""
    auto_explore = self.request.get('auto_explore') == '1'
    bug_id = self.request.get('bug_id')

    change_1 = {
        'base_commit': {
            'repository': self.request.get('start_repository'),
            'git_hash': self.request.get('start_git_hash')
        }
    }

    change_2 = {
        'base_commit': {
            'repository': self.request.get('end_repository'),
            'git_hash': self.request.get('end_git_hash')
        }
    }

    # Validate arguments and convert them to canonical internal representation.
    quest_generator = quest_generator_module.QuestGenerator(self.request)
    bug_id = self._ValidateBugId(bug_id)
    changes = self._ValidateChanges(change_1, change_2)

    # Create job.
    job = job_module.Job.New(
        arguments=quest_generator.AsDict(),
        quests=quest_generator.Quests(),
        auto_explore=auto_explore,
        bug_id=bug_id)

    # Add changes.
    for c in changes:
      job.AddChange(c)

    # Put job into datastore.
    job_id = job.put().urlsafe()

    # Start job.
    job.Start()
    job.put()

    # TODO: Figure out if these should be underscores or lowerCamelCase.
    # TODO: They should match the input arguments.
    self.response.out.write(json.dumps({
        'jobId': job_id,
        'jobUrl': job.url
    }))

  def _ValidateBugId(self, bug_id):
    if not bug_id:
      return None

    try:
      return int(bug_id)
    except ValueError:
      raise ValueError(_ERROR_BUG_ID)

  def _ValidateChanges(self, change_1, change_2):
    return (change.Change.FromDict(change_1), change.Change.FromDict(change_2))
