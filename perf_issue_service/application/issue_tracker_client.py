# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a layer of abstraction for the issue tracker API."""

from http import client as http_client
import json
import logging

from apiclient import discovery
from apiclient import errors
from application import utils

_DISCOVERY_URI = ('https://monorail-prod.appspot.com'
                  '/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest')

STATUS_DUPLICATE = 'Duplicate'
MAX_DISCOVERY_RETRIES = 3
MAX_REQUEST_RETRIES = 5


class IssueTrackerClient:
  """Class for updating bug issues."""

  def __init__(self):
    """Initializes an object for communicate to the issue tracker.

    This object can be re-used to make multiple requests without calling
    apliclient.discovery.build multiple times.

    This class makes requests to the Monorail API.
    API explorer: https://goo.gl/xWd0dX

    Args:
      http: A Http object that requests will be made through; this should be an
          Http object that's already authenticated via OAuth2.
    """
    http = utils.ServiceAccountHttp()
    http.timeout = 30

    # Retry connecting at least 3 times.
    attempt = 1
    while attempt != MAX_DISCOVERY_RETRIES:
      try:
        self._service = discovery.build(
            'monorail', 'v1', discoveryServiceUrl=_DISCOVERY_URI, http=http)
        break
      except http_client.HTTPException as e:
        logging.error('Attempt #%d: %s', attempt, e)
        if attempt == MAX_DISCOVERY_RETRIES:
          raise
      attempt += 1

  def GetIssuesList(self, project='chromium', **kwargs):
    """Makes a request to the issue tracker to list bugs."""
    # Normalize the project in case it is empty or None.
    project = 'chromium' if project is None or not project.strip() else project
    request = self._service.issues().list(projectId=project, **kwargs)
    response = self._ExecuteRequest(request)
    return response.get('items', []) if response else []


  def GetIssue(self, issue_id, project='chromium'):
    """Makes a request to the issue tracker to get an issue."""
    # Normalize the project in case it is empty or None.
    project = 'chromium' if project is None or not project.strip() else project
    request = self._service.issues().get(projectId=project, issueId=issue_id)
    return self._ExecuteRequest(request)


  def GetIssueComments(self, issue_id, project='chromium'):
    """Gets all the comments for the given bug.

    Args:
      issue_id: Bug ID of the issue to update.

    Returns:
      A list of comments
    """
    request = self._service.issues().comments().list(
        projectId=project, issueId=issue_id, maxResults=1000)
    response = self._ExecuteRequest(request)
    if not response:
      return None
    return [{
        'id': r['id'],
        'author': r['author'].get('name'),
        'content': r['content'],
        'published': r['published'],
        'updates': r['updates']
    } for r in response.get('items')]


  def _ExecuteRequest(self, request):
    """Makes a request to the issue tracker.

    Args:
      request: The request object, which has a execute method.

    Returns:
      The response if there was one, or else None.
    """
    response = request.execute(
        num_retries=MAX_REQUEST_RETRIES, http=utils.ServiceAccountHttp())
    return response
