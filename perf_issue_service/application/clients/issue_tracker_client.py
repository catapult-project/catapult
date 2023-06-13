# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a layer of abstraction for the issue tracker API."""

import logging

from application.clients import monorail_client
from application.clients import buganizer_client

BUGANIZER_PROJECTS = {
  "MigratedProject": "buganizer",
  "ReadOnlyProject": "none"
}

class IssueTrackerClient:
  """Class for updating perf issues."""

  def __init__(self, project_name='chromium'):
    issue_tracker_service = self._GetIssueTrackerByProject(project_name)
    if issue_tracker_service == 'monorail':
      self._client = monorail_client.MonorailClient()
    elif issue_tracker_service == 'buganizer':
      self._client = buganizer_client.BuganizerClient()
    else:
      raise NotImplementedError(
        'Unknow issue tracker service target: %s', issue_tracker_service)


  def _GetIssueTrackerByProject(self, project_name):
    issue_tracker = BUGANIZER_PROJECTS.get(project_name, 'monorail')
    logging.debug(
      '[PerfIssueService] Project %s is using %s as issue tracker.',
      project_name, issue_tracker)
    return issue_tracker


  def GetIssuesList(self, **kwargs):
    """Makes a request to the issue tracker to list issues."""
    return self._client.GetIssuesList(**kwargs)

  def GetIssue(self, **kwargs):
    """Makes a request to the issue tracker to get an issue."""
    return self._client.GetIssue(**kwargs)

  def GetIssueComments(self, **kwargs):
    """Gets all the comments for the given issue."""
    return self._client.GetIssueComments(**kwargs)

  def NewIssue(self, **kwargs):
    """Create a new issue."""
    return self._client.NewIssue(**kwargs)

  def NewComment(self, **kwargs):
    """Create a new comment for the targeted issue"""
    return self._client.NewComment(**kwargs)

