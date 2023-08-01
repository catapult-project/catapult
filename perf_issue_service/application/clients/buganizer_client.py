# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a layer of abstraction for the buganizer API."""

from http import client as http_client
import json
import logging

from apiclient import discovery
from application import utils
from application import buganizer_utils as b_utils


_DISCOVERY_URI = ('https://issuetracker.googleapis.com/$discovery/rest?version=v1&labels=GOOGLE_PUBLIC')

BUGANIZER_SCOPES = 'https://www.googleapis.com/auth/buganizer'
MAX_DISCOVERY_RETRIES = 3
MAX_REQUEST_RETRIES = 5


class BuganizerClient:
  """Class for updating perf issues."""

  def __init__(self):
    """Initializes an object for communicate to the Buganizer.
    """
    http = utils.ServiceAccountHttp(BUGANIZER_SCOPES)
    http.timeout = 30

    # Retry connecting at least 3 times.
    attempt = 1
    while attempt != MAX_DISCOVERY_RETRIES:
      try:
        self._service = discovery.build(
            'issuetracker', 'v1', discoveryServiceUrl=_DISCOVERY_URI, http=http)
        break
      except http_client.HTTPException as e:
        logging.error('Attempt #%d: %s', attempt, e)
        if attempt == MAX_DISCOVERY_RETRIES:
          raise
      attempt += 1


  def GetIssuesList(self, limit, age, status, labels, project='chromium'):
    """Makes a request to the issue tracker to list issues.

    Args:
      limit: the limit of results to fetch
      age: the number of days after the issue was created
      status: the status of the issues
      labels: the labels (hotlists) of the issue.
              The term 'labels' is what we use in Monorail and it is no longer
              available in Buganizer. Instead, we will use hotlists.
      project: the project name in Monorail. It is not needed in Buganizer. We
              will use it to look for the corresponding 'component'.

    Returns:
      a list of issues.
      (The issues are now in Monorail format before consumers are updated.)
    """
    project = 'chromium' if project is None or not project.strip() else project

    components = b_utils.FindBuganizerComponents(monorail_project_name=project)
    if not components:
      logging.warning(
        '[Buganizer API] Failed to find components for the given project: %s',
        project)
      return []
    components_string = '|'.join(components)
    query_string = 'componentid:%s' % components_string

    # by default, buganizer return all.
    if status and status != 'all':
      query_string += ' AND status:%s' % status

    if age:
      query_string += ' AND created:%sd' % age

    if labels:
      label_list = labels.split(',')
      hotlists = b_utils.FindBuganizerHotlists(label_list)
      if hotlists:
        query_string += ' AND hotlistid:%s' % '|'.join(hotlists)

    logging.info('[PerfIssueService] GetIssueList Query: %s', query_string)
    request = self._service.issues().list(
      query=query_string,
      pageSize=min(500, int(limit)),
      view='FULL'
    )
    response = self._ExecuteRequest(request)

    buganizer_issues = response.get('issues', []) if response else []

    logging.debug('Buganizer Issues: %s', buganizer_issues)

    monorail_issues = [
      b_utils.ReconcileBuganizerIssue(issue) for issue in buganizer_issues]

    return monorail_issues


  def GetIssue(self, issue_id, project='chromium'):
    """Makes a request to the issue tracker to get an issue.

    Args:
      issue_id: the id of the issue

    Returns:
      an issue.
      (The issues are now in Monorail format before consumers are updated.)
    """
    del project
    request = self._service.issues().get(issueId=issue_id, view='FULL')
    buganizer_issue = self._ExecuteRequest(request)

    logging.debug('Buganizer Comments for %s: %s', issue_id, buganizer_issue)

    monorail_issue = b_utils.ReconcileBuganizerIssue(buganizer_issue)

    return monorail_issue


  def GetIssueComments(self, issue_id, project='chromium'):
    """Gets all the comments for the given issue.

    The GetIssueComments is used only in the alert group workflow to check
    whether the issue is closed by Pinpoint (chromeperf's service account).
    Unlike Monorail, status update and comments are two independent workflows
    in Buganizer. As the existing workflow only looks for the status update,
    we will get the issue updates instead of issue comments.
    To avoid changes on client side, I keep the field name in 'comments' in
    the return value.

    Args:
      issue_id: the id of the issue.

    Returns:
      a list of updates of the issue.
    (The updates are now in Monorail format before consumers are updated.)
    """
    del project

    request = self._service.issues().issueUpdates().list(issueId=issue_id)
    response = self._ExecuteRequest(request)

    logging.debug('Buganizer Issue for %s: %s', issue_id, response)

    schema = self._service._schema.get('IssueState')
    status_enum = schema['properties']['status']['enum']

    if not response:
      return []

    return [{
        'id': update.get('version'),
        'author': update.get('author', {}).get('emailAddress', ''),
        'content': update.get('issueComment', {}).get('comment', ''),
        'published': update.get('timestamp'),
        'updates': b_utils.GetBuganizerStatusUpdate(update, status_enum) or {}
    } for update in response.get('issueUpdates')]


  def NewIssue(self,
             title,
             description,
             project='chromium',
             labels=None,
             components=None,
             owner=None,
             cc=None,
             status=None):
    raise NotImplementedError('Buganizer API is under construction..')

  def NewComment(self,
                  issue_id,
                  project='chromium',
                  comment='',
                  title=None,
                  status=None,
                  merge_issue=None,
                  owner=None,
                  cc=None,
                  components=None,
                  labels=None,
                  send_email=True):
    raise NotImplementedError('Buganizer API is under construction..')

  def _ExecuteRequest(self, request):
    """Makes a request to the issue tracker.

    Args:
      request: The request object, which has a execute method.

    Returns:
      The response if there was one, or else None.
    """
    response = request.execute(
        num_retries=MAX_REQUEST_RETRIES,
        http=utils.ServiceAccountHttp(BUGANIZER_SCOPES))
    return response
