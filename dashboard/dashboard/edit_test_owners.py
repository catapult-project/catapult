# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for adding and removing test owners."""

import json

from google.appengine.api import users

from dashboard import request_handler
from dashboard import test_owner
from dashboard import xsrf


class EditTestOwnersHandler(request_handler.RequestHandler):
  """Handles rendering and editing test owners."""

  def get(self):
    """Renders the UI for editing owners.

    If user is an admin, renders UI with all test suite path and its owners,
    otherwise renders UI with a list test suite path for the logged in user.
    """
    user = users.get_current_user()
    if user:
      if users.is_current_user_admin():
        owner_json = self._GetAllOwnerDataJson()
      else:
        owner_json = self._GetOwnerDataForUserJson(user)
    else:
      self.RenderHtml('result.html', {
          'errors': ['Log in to edit test owners.']})
      return

    self.RenderHtml('edit_test_owners.html',
                    {'owner_info': owner_json})

  @xsrf.TokenRequired
  def post(self):
    """Handles updates of test owners."""
    user = users.get_current_user()
    if not user:
      self.ReportError('Must be logged in to edit test owners.', status=403)
      return

    action = self.request.get('action')
    test_suite_path = self.request.get('item')

    if not action or not test_suite_path:
      self.ReportError('Missing required parameters.', status=403)
      return

    owner_email = self.request.get('sub_item')
    if not users.is_current_user_admin():
      owner_email = user.email()

    test_suite_path = str(test_suite_path)
    owner_email = str(owner_email) if owner_email else None
    try:
      test_owner.ValidateTestSuitePath(test_suite_path)
      test_owner.ValidateOwnerEmail(owner_email)
    except ValueError as error:
      self.ReportError(error.message, status=400)
      return

    if action == 'add':
      test_owner.AddOwner(test_suite_path, owner_email)
    else:
      test_owner.RemoveOwner(test_suite_path, owner_email)

    self.response.out.write('{}')

  def _GetOwnerDataForUserJson(self, user):
    """Returns json list of owner data for a user."""
    results = []
    owner_email = user.email()
    test_suite_paths = test_owner.GetTestSuitePaths(owner_email)
    for test_suite_path in sorted(test_suite_paths):
      results.append({
          'name': test_suite_path,
      })
    return json.dumps(results)

  def _GetAllOwnerDataJson(self):
    """Returns json list of all owner data."""
    owner_dict = test_owner.GetMasterCachedOwner()
    results = []
    for test_suite_path in sorted(owner_dict):
      owners = owner_dict[test_suite_path]
      item = {
          'name': test_suite_path,
          'sub_items': []
      }
      for owner in owners:
        item['sub_items'].append({
            'name': owner
        })
      results.append(item)
    return json.dumps(results)
