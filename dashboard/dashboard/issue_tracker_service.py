# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides a layer of abstraction for the issue tracker API."""

import logging

from apiclient import discovery
from apiclient import errors
import httplib2


class IssueTrackerService(object):
  """Class for updating bug issues."""

  def __init__(self, http=None, additional_credentials=None):
    """Initializes an object for adding and updating bugs on the issue tracker.

    This object can be re-used to make multiple requests without calling
    apliclient.discovery.build multiple times.

    This class makes requests to the Project Hosting API. Project hosting is
    another name for Google Code, which includes the issue tracker used by
    Chromium. API explorer:
    http://developers.google.com/apis-explorer/#s/projecthosting/v2/

    Args:
      http: A Http object to pass to request.execute.
      additional_credentials: A credentials object, e.g. an instance of
          oauth2client.client.SignedJwtAssertionCredentials.
    """
    self._http = http or httplib2.Http()
    if additional_credentials:
      additional_credentials.authorize(self._http)
    self._service = discovery.build('projecthosting', 'v2')

  def AddBugComment(self, bug_id, comment, status=None,
                    cc_list=None, merge_issue=None, labels=None,
                    owner=None):
    """Adds a comment with the bisect results to the given bug.

    Args:
      bug_id: Bug ID of the issue to update.
      comment: Bisect results information.
      status: A string status for bug, e.g. Assigned, Duplicate, WontFix, etc.
      cc_list: List of email addresses of users to add to the CC list.
      merge_issue: ID of the issue to be merged into; specifying this option
          implies that the status should be "Duplicate".
      labels: List of labels for bug.
      owner: Owner of the bug.

    Returns:
      True if successful, False otherwise.
    """
    if not bug_id or bug_id < 0:
      return False

    body = {'content': comment}
    updates = {}
    # Mark issue as duplicate when relevant bug ID is found in the datastore.
    # Avoid marking an issue as duplicate of itself.
    if merge_issue and int(merge_issue) != bug_id:
      status = 'Duplicate'
      updates['mergedInto'] = merge_issue
      logging.info('Bug %s marked as duplicate of %s', bug_id, merge_issue)
    if status:
      updates['status'] = status
    if cc_list:
      updates['cc'] = cc_list
    if labels:
      updates['labels'] = labels
    if owner:
      updates['owner'] = owner
    body['updates'] = updates

    return self._MakeCommentRequest(bug_id, body)

  def _MakeCommentRequest(self, bug_id, body):
    """Make a request to the issue tracker to update a bug."""
    request = self._service.issues().comments().insert(
        projectId='chromium',
        issueId=bug_id,
        body=body)
    response = self._ExecuteRequest(request)
    if not response:
      logging.error('Error updating bug %s with body %s', bug_id, body)
      return False
    return True

  def NewBug(self, title, description, labels=None, owner=None):
    """Creates a new bug.

    Args:
      title: The short title text of the bug.
      description: The body text for the bug.
      labels: Starting labels for the bug.
      owner: Starting owner account name.

    Returns:
      The new bug ID if successfully created, or None.
    """
    body = {
        'title': title,
        'summary': title,
        'description': description,
        'labels': labels or [],
        'status': 'Assigned',
    }
    if owner:
      body['owner'] = {'name': owner}
    return self._MakeCreateRequest(body)

  def _MakeCreateRequest(self, body):
    """Makes a request to create a new bug.

    Args:
      body: The request body parameter dictionary.

    Returns:
      A bug ID if successful, or None otherwise.
    """
    request = self._service.issues().insert(projectId='chromium', body=body)
    response = self._ExecuteRequest(request)
    if response and 'id' in response:
      return response['id']
    return None

  def _ExecuteRequest(self, request):
    """Make a request to the issue tracker.

    Args:
      request: The request object, which has a execute method.

    Returns:
      The response if there was one, or else None.
    """
    try:
      response = request.execute(http=self._http)
      return response
    except errors.HttpError as e:
      logging.error(e)
      return None
