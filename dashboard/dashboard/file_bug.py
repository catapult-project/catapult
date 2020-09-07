# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for filing a bug on the issue tracker."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from google.appengine.api import users
from google.appengine.ext import ndb

from dashboard import oauth2_decorator
from dashboard.common import file_bug
from dashboard.common import request_handler
from dashboard.common import utils


class FileBugHandler(request_handler.RequestHandler):
  """Uses oauth2 to file a new bug with a set of alerts."""

  def post(self):
    """A POST request for this endpoint is the same as a GET request."""
    self.get()

  @oauth2_decorator.DECORATOR.oauth_required
  def get(self):
    """Either shows the form to file a bug, or if filled in, files the bug.

    The form to file a bug is popped up from the triage-dialog polymer element.
    The default summary, description and label strings are constructed there.

    Request parameters:
      summary: Bug summary string.
      description: Bug full description string.
      keys: Comma-separated Alert keys in urlsafe format.
      finish: Boolean set to true when creating a bug, false otherwise.
      project_id: The Monorail project ID (used to create  a bug).
      labels: Bug labels (used to create  a bug).
      components: Bug components (used to create  a bug).
      owner: Bug owner email address (used to create  a bug).
      cc: Bug emails to CC (used to create  a bug).

    Outputs:
      HTML, using the template 'bug_result.html'.
    """
    if not utils.IsValidSheriffUser():
      self.RenderHtml(
          'bug_result.html', {
              'error': 'You must be logged in with a chromium.org account '
                       'to file bugs.'
          })
      return

    summary = self.request.get('summary')
    description = self.request.get('description')
    keys = self.request.get('keys')

    if not keys:
      self.RenderHtml('bug_result.html',
                      {'error': 'No alerts specified to add bugs to.'})
      return

    if self.request.get('finish'):
      project_id = self.request.get('project_id', 'chromium')
      labels = self.request.get_all('label')
      components = self.request.get_all('component')
      owner = self.request.get('owner')
      cc = self.request.get('cc')
      self._CreateBug(owner, cc, summary, description, project_id, labels,
                      components, keys)
    else:
      self._ShowBugDialog(summary, description, keys)

  def _ShowBugDialog(self, summary, description, urlsafe_keys):
    """Sends a HTML page with a form for filing the bug.

    Args:
      summary: The default bug summary string.
      description: The default bug description string.
      urlsafe_keys: Comma-separated Alert keys in urlsafe format.
    """
    alert_keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys.split(',')]
    labels, components = file_bug.FetchLabelsAndComponents(alert_keys)
    owner_components = file_bug.FetchBugComponents(alert_keys)
    self.RenderHtml(
        'bug_result.html', {
            'bug_create_form': True,
            'keys': urlsafe_keys,
            'summary': summary,
            'description': description,
            'projects': utils.MONORAIL_PROJECTS,
            'labels': labels,
            'components': components.union(owner_components),
            'owner': '',
            'cc': users.get_current_user(),
        })

  def _CreateBug(self, owner, cc, summary, description, project_id, labels,
                 components, urlsafe_keys):
    """Creates a bug, associates it with the alerts, sends a HTML response.

    Args:
      owner: The owner of the bug, must end with @{project_id}.org or
        @google.com if not empty.
      cc: CSV of email addresses to CC on the bug.
      summary: The new bug summary string.
      description: The new bug description string.
      project_id: The Monorail project ID used to create the bug.
      labels: List of label strings for the new bug.
      components: List of component strings for the new bug.
      urlsafe_keys: Comma-separated alert keys in urlsafe format.
    """
    # Only project members (@{project_id}.org or @google.com accounts)
    # can be owners of bugs.
    project_domain = '@%s.org' % project_id
    if owner and not owner.endswith(project_domain) and not owner.endswith(
        '@google.com'):
      self.RenderHtml(
          'bug_result.html', {
              'error':
                  'Owner email address must end with %s or @google.com.' %
                  project_domain
          })
      return

    http = oauth2_decorator.DECORATOR.http()
    template_params = file_bug.FileBug(http, owner, cc, summary, description,
                                       project_id, labels, components,
                                       urlsafe_keys.split(','))
    self.RenderHtml('bug_result.html', template_params)
