# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for setting a warning message for all users.

This should be used by perf sheriffs and speed infra team to set appropriate
warning messages when parts of our infrastructure are down.
"""

from dashboard import layered_cache
from dashboard import request_handler
from dashboard import utils

_DAYS_TO_SHOW_MESSAGE = 3


class SetWarningMessageHandler(request_handler.RequestHandler):
  """Allows internal users to set and delete warning messages.

  Warning messages are shown on /report page, to warn users of outages and
  planned maintenance.
  """

  def get(self):
    """Renders the UI for setting the warning message."""
    if self._ShowErrorIfNotLoggedIn():
      return
    self.RenderHtml('set_warning_message.html', {
        'warning_message': layered_cache.Get('warning_message') or '',
        'warning_bug': layered_cache.Get('warning_bug') or '',
    })

  def post(self):
    """Handles a request to set the warning message."""
    if self._ShowErrorIfNotLoggedIn():
      return
    message = self.request.get('warning_message')
    if not message:
      layered_cache.Delete('warning_message')
      layered_cache.Delete('warning_bug')
      self.RenderHtml('result.html', {'headline': 'Warning message cleared.'})
    else:
      results = [{'name': 'Warning message', 'value': message}]
      layered_cache.Set('warning_message', message, _DAYS_TO_SHOW_MESSAGE)
      bug = self.request.get('warning_bug')
      if bug:
        layered_cache.Set('warning_bug', bug, _DAYS_TO_SHOW_MESSAGE)
        results.append({'name': 'Bug ID', 'value': bug})
      else:
        layered_cache.Delete('warning_bug')
      self.RenderHtml('result.html', {
          'headline': 'Warning message set.',
          'results': results
      })

  def _ShowErrorIfNotLoggedIn(self):
    """Shows an error message if not logged in with an internal account.

    Returns:
      True if error message shown, False otherwise.
    """
    if not utils.IsInternalUser():
      self.RenderHtml('result.html', {
          'errors': ['Only logged-in internal users can set warnings.']
      })
      return True
    return False
