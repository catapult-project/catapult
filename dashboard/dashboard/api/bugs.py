# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.api import api_request_handler
from dashboard.api import utils as api_utils
from dashboard.common import datastore_hooks
from dashboard.common import utils
from dashboard.services import issue_tracker_service


class BugsHandler(api_request_handler.ApiRequestHandler):
  """API handler for bug requests.

  Convenience methods for getting bug data; only available to internal users.
  """

  def _CheckUser(self):
    self._CheckIsLoggedIn()
    if not datastore_hooks.IsUnalteredQueryPermitted():
      raise api_request_handler.ForbiddenError()

  def Post(self, bug_id, *unused_args):
    """Returns alert data in response to API requests.

    Argument:
      bug_id: issue id on the chromium issue tracker

    Outputs:
      JSON data for the bug, see README.md.
    """
    service = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())

    if bug_id == 'recent':
      response = service.List(
          q='opened-after:today-5',
          label='Type-Bug-Regression,Performance',
          sort='-id')
      return {'bugs': response.get('items', [])}

    try:
      bug_id = int(bug_id)
    except ValueError:
      raise api_request_handler.BadRequestError(
          'Invalid bug ID "%s".' % bug_id)

    try:
      include_comments = api_utils.ParseBool(
          self.request.get('include_comments', None))
    except ValueError:
      raise api_request_handler.BadRequestError(
          "value of |with_comments| should be 'true' or 'false'")

    issue = service.GetIssue(bug_id)
    bisects = []

    def _FormatDate(d):
      if not d:
        return ''
      return d.isoformat()

    response = {'bug': {
        'author': issue.get('author', {}).get('name'),
        'owner': issue.get('owner', {}).get('name'),
        'legacy_bisects': [{
            'status': b.status,
            'bot': b.bot,
            'bug_id': b.bug_id,
            'buildbucket_link': (
                'https://chromeperf.appspot.com/buildbucket_job_status/%s' %
                b.buildbucket_job_id),
            'command': b.GetConfigDict()['command'],
            'culprit': None,
            'metric': (b.results_data or {}).get('metric'),
            'started_timestamp': _FormatDate(b.last_ran_timestamp),
        } for b in bisects],
        'cc': [cc.get('name') for cc in issue.get('cc', [])],
        'components': issue.get('components', []),
        'id': bug_id,
        'labels': issue.get('labels', []),
        'published': issue.get('published'),
        'updated': issue.get('updated'),
        'state': issue.get('state'),
        'status': issue.get('status'),
        'summary': issue.get('summary'),
    }}

    if include_comments:
      comments = service.GetIssueComments(bug_id)
      response['bug']['comments'] = [{
          'content': comment.get('content'),
          'author': comment.get('author'),
          'published': comment.get('published'),
      } for comment in comments]

    return response
