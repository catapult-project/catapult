# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

import application
from application.app import create_app

class IssuesTest(unittest.TestCase):

  def setUp(self):
    self.client = create_app().test_client()

  @mock.patch('application.issue_tracker_client.IssueTrackerClient')
  def testIssueGetHandlerArgumentsDefault(self, mock_client):
    instance = mock_client.return_value
    instance.GetIssuesList.side_effect = []

    response = self.client.get('/issues/')
    data = response.get_data(as_text=True)
    instance.GetIssuesList.assert_called_once_with(
      q='opened>today-3',
      can='open',
      label='',
      maxResults='2000',
      sort='-id'
    )

  @mock.patch('application.issue_tracker_client.IssueTrackerClient')
  def testIssueGetHandlerArguments(self, mock_client):
    instance = mock_client.return_value
    instance.GetIssuesList.side_effect = []

    response = self.client.get(
      '/issues/?limit=123&age=456&labels=abc,xyz')
    data = response.get_data(as_text=True)
    instance.GetIssuesList.assert_called_once_with(
      q='opened>today-456',
      can='open',
      label='abc,xyz',
      maxResults='123',
      sort='-id'
    )

  @mock.patch('application.issue_tracker_client.IssueTrackerClient')
  def testIssueGetByIdHandler(self, mock_client):
    instance = mock_client.return_value
    instance.GetIssue.side_effect = []

    response = self.client.get(
      '/issues/12345/project/foo')
    data = response.get_data(as_text=True)
    instance.GetIssue.assert_called_once_with(
      issue_id='12345',
      project='foo',
    )

  @mock.patch('application.issue_tracker_client.IssueTrackerClient')
  def testCommentsGetByIdHandler(self, mock_client):
    instance = mock_client.return_value
    instance.GetIssueComments.side_effect = []

    response = self.client.get(
      '/issues/12345/project/foo/comments')
    data = response.get_data(as_text=True)
    instance.GetIssueComments.assert_called_once_with(
      issue_id='12345',
      project='foo',
    )