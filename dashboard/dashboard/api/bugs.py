# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json

from dashboard.api import api_auth
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import try_job
from dashboard.services import issue_tracker_service


class BadRequestError(Exception):
  pass


class BugsHandler(request_handler.RequestHandler):
  """API handler for bug requests.

  Convenience methods for getting bug data; only available to internal users.
  """

  def post(self, *args):
    """Returns alert data in response to API requests.

    Argument:
      bug_id: issue id on the chromium issue tracker

    Outputs:
      JSON data for the bug, see README.md.
    """
    try:
      bug = self._GetBug(*args)
      self.response.out.write(json.dumps({'bug': bug}))
    except BadRequestError as e:
      self._WriteErrorMessage(e.message, 500)
    except api_auth.NotLoggedInError:
      self._WriteErrorMessage('User not authenticated', 403)
    except api_auth.OAuthError:
      self._WriteErrorMessage('User authentication error', 403)

  @api_auth.Authorize
  def _GetBug(self, *args):
    # Users must log in with privileged access to see all bugs.
    if not datastore_hooks.IsUnalteredQueryPermitted():
      raise BadRequestError('No access.')

    try:
      bug_id = int(args[0])
    except ValueError:
      raise BadRequestError('Invalid bug ID "%s".' % args[0])
    service = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
    issue = service.GetIssue(bug_id)
    comments = service.GetIssueComments(bug_id)
    bisects = try_job.TryJob.query(try_job.TryJob.bug_id == bug_id).fetch()
    return {
        'author': issue.get('author', {}).get('name'),
        'legacy_bisects': [{
            'status': b.status,
            'bot': b.bot,
            'bug_id': b.bug_id,
            'buildbucket_link': (
                'https://chromeperf.appspot.com/buildbucket_job_status/%s' %
                b.buildbucket_job_id),
            'command': b.GetConfigDict()['command'],
            'culprit': self._GetCulpritInfo(b),
            'metric': (b.results_data or {}).get('metric'),
        } for b in bisects],
        'cc': [cc.get('name') for cc in issue.get('cc', [])],
        'comments': [{
            'content': comment.get('content'),
            'author': comment.get('author'),
            'published': self._FormatTimestampMilliseconds(
                comment.get('published')),
        } for comment in comments],
        'components': issue.get('components', []),
        'id': bug_id,
        'labels': issue.get('labels', []),
        'published': self._FormatTimestampMilliseconds(issue.get('published')),
        'state': issue.get('state'),
        'status': issue.get('status'),
        'summary': issue.get('summary'),
    }

  def _WriteErrorMessage(self, message, status):
    self.ReportError(message, status=status)
    self.response.out.write(json.dumps({'error': message}))

  def _FormatTimestampMilliseconds(self, timestamp_string):
    time = datetime.datetime.strptime(timestamp_string, '%Y-%m-%dT%H:%M:%S')
    return utils.TimestampMilliseconds(time)

  def _GetCulpritInfo(self, try_job_entity):
    if not try_job_entity.results_data:
      return None
    culprit = try_job_entity.results_data.get('culprit_data')
    if not culprit:
      return None
    return {
        'cl': culprit.get('cl'),
        'subject': culprit.get('subject'),
    }

