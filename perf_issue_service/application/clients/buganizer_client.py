# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a layer of abstraction for the buganizer API."""

from http import client as http_client
import json
import logging

from apiclient import discovery
from application import utils


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
    """Makes a request to the issue tracker to list issues."""
    del labels  # removed for now as the hotlist are not ready
    project = 'chromium' if project is None or not project.strip() else project
    components = utils.FindBuganizerComponents(project_name=project)
    if not components:
      logging.warning(
        '[Buganizer API] Failed to find components for the given project: %s',
        project)
      return []
    components_string = '|'.join(components)

    query_string = 'componentid:%s' % components_string
    if status:
      query_string += ' AND status:%s' % status
    if age:
      query_string += ' AND created:%sd' % age

    request = self._service.issues().list(
      query=query_string,
      pageSize=min(500, int(limit))
    )
    response = self._ExecuteRequest(request)

    return response

  def GetIssue(self, issue_id, project='chromium'):
    """Makes a request to the issue tracker to get an issue."""
    del project
    request = self._service.issues().get(issueId=issue_id)
    response = self._ExecuteRequest(request)

    return response

  def GetIssueComments(self, issue_id, project='chromium', page_size=200):
    """Gets all the comments for the given issue."""
    del project
    request = self._service.issues().comments().list(
      issueId=issue_id, pageSize=200)
    response = self._ExecuteRequest(request)

    if not response:
      return None
    return [{
        'id': comment.get('commentNumber'),
        'author': 'Not Yet Exposed',
        'content': comment.get('comment', ''),
        'published': 'Not Yet Exposed',
        'updates': 'Not Yet Exposed'
    } for comment in response.get('issueComments')]

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
