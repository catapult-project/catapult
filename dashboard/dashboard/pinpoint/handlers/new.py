# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.api import api_auth
from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import quest as quest_module


_ERROR_BUG_ID = 'Bug ID must be an integer.'
_ERROR_TAGS_DICT = 'Tags must be a dict of key/value string pairs.'


class New(webapp2.RequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def post(self):
    try:
      self._CreateJob()
    except (api_auth.ApiAuthException, KeyError, TypeError, ValueError) as e:
      self._WriteErrorMessage(e.message)

  def _WriteErrorMessage(self, message):
    self.response.out.write(json.dumps({'error': message}))

  def _CreateJob(self):
    """Start a new Pinpoint job."""
    auto_explore = _ParseBool(self.request.get('auto_explore'))
    bug_id = self.request.get('bug_id')

    # Validate arguments and convert them to canonical internal representation.
    arguments, quests = _GenerateQuests(self.request.params)
    bug_id = _ValidateBugId(bug_id)
    changes = _ValidateChanges(self.request.params)
    tags = _ValidateTags(self.request.get('tags'))

    # Create job.
    job = job_module.Job.New(
        arguments=arguments,
        quests=quests,
        auto_explore=auto_explore,
        bug_id=bug_id,
        tags=tags)

    # Add changes.
    for c in changes:
      job.AddChange(c)

    # Put job into datastore.
    job.put()

    # Start job.
    job.Start()
    job.put()

    self.response.out.write(json.dumps({
        'jobId': job.job_id,
        'jobUrl': job.url,
    }))


def _ParseBool(value):
  return value == '1' or value.lower() == 'true'


def _ValidateTags(tags):
  if not tags:
    return {}

  tags_dict = json.loads(tags)

  if not isinstance(tags_dict, dict):
    raise ValueError(_ERROR_TAGS_DICT)

  for k, v in tags_dict.iteritems():
    if not isinstance(k, basestring) or not isinstance(v, basestring):
      raise ValueError(_ERROR_TAGS_DICT)

  return tags_dict


def _ValidateBugId(bug_id):
  if not bug_id:
    return None

  try:
    return int(bug_id)
  except ValueError:
    raise ValueError(_ERROR_BUG_ID)


def _ValidateChanges(arguments):
  changes = arguments.get('changes')
  if changes:
    return [change.Change.FromDict(c) for c in json.loads(changes)]

  change_1 = {
      'commits': [{
          'repository': arguments.get('start_repository'),
          'git_hash': arguments.get('start_git_hash')
      }],
  }

  change_2 = {
      'commits': [{
          'repository': arguments.get('end_repository'),
          'git_hash': arguments.get('end_git_hash')
      }]
  }

  if arguments.get('patch'):
    change_2['patch'] = arguments.get('patch')

  return (change.Change.FromDict(change_1), change.Change.FromDict(change_2))


def _GenerateQuests(arguments):
  """Generate a list of Quests from a dict of arguments.

  GenerateQuests uses the arguments to infer what types of Quests the user wants
  to run, and creates a list of Quests with the given configuration.

  Arguments:
    arguments: A dict or MultiDict containing arguments.

  Returns:
    A tuple of (arguments, quests), where arguments is a dict containing the
    request arguments that were used, and quests is a list of Quests.
  """
  target = arguments.get('target')
  if target in ('telemetry_perf_tests', 'telemetry_perf_webview_tests'):
    quest_classes = (quest_module.FindIsolate, quest_module.RunTest,
                     quest_module.ReadHistogramsJsonValue)
  else:
    quest_classes = (quest_module.FindIsolate, quest_module.RunTest,
                     quest_module.ReadGraphJsonValue)

  used_arguments = {}
  quests = []
  for quest_class in quest_classes:
    quest_arguments, quest = quest_class.FromDict(arguments)
    if not quest:
      return used_arguments, quests
    used_arguments.update(quest_arguments)
    quests.append(quest)

  return used_arguments, quests
