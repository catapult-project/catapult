# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for adding and editing sheriff rotations."""

import json

from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.api import users

from dashboard import namespaced_stored_object
from dashboard import request_handler
from dashboard import stored_object
from dashboard import utils
from dashboard import xsrf

_NOTIFICATION_EMAIL_BODY = """
The configuration of %(hostname)s was changed by %(user)s.
Here are the new values:

Key: %(key)s

Non-namespaced value:
%(value)s

Externally-visible value:
%(external_value)s

Internal-only value:
%(internal_value)s
"""

# TODO(qyearsley): Make this customizable by storing the value in datastore.
# Make sure to send a notification to both old and new address if this value
# gets changed.
_NOTIFICATION_ADDRESS = 'chrome-perf-dashboard-alerts@google.com'
_SENDER_ADDRESS = 'gasper-alerts@google.com'


class EditSiteConfigHandler(request_handler.RequestHandler):
  """Handles editing of site config values stored with stored_entity."""

  def get(self):
    """Renders the UI with the form."""
    key = self.request.get('key')
    if not key:
      self.RenderHtml('edit_site_config.html', {})
      return

    value = stored_object.Get(key)
    external_value = namespaced_stored_object.GetExternal(key)
    internal_value = namespaced_stored_object.Get(key)
    self.RenderHtml('edit_site_config.html', {
        'key': key,
        'value': _FormatJson(value),
        'external_value': _FormatJson(external_value),
        'internal_value': _FormatJson(internal_value),
    })

  @xsrf.TokenRequired
  def post(self):
    """Accepts posted values, makes changes, and shows the form again."""
    key = self.request.get('key')

    if not utils.IsInternalUser():
      self.RenderHtml('edit_site_config.html', {
          'error': 'Only internal users can post to this end-point.'
      })
      return

    if not key:
      self.RenderHtml('edit_site_config.html', {})
      return

    value = self.request.get('value').strip()
    external_value = self.request.get('external_value').strip()
    internal_value = self.request.get('internal_value').strip()
    template_params = {
        'key': key,
        'value': value,
        'external_value': external_value,
        'internal_value': internal_value,
    }

    try:
      if value:
        stored_object.Set(key, json.loads(value))
      if external_value:
        namespaced_stored_object.SetExternal(key, json.loads(external_value))
      if internal_value:
        namespaced_stored_object.Set(key, json.loads(internal_value))
    except ValueError:
      template_params['error'] = 'Invalid JSON in at least one field.'

    _SendNotificationEmail(key, template_params)
    self.RenderHtml('edit_site_config.html', template_params)


def _SendNotificationEmail(key, email_body_params):
  user_email = users.get_current_user().email()
  subject = 'Config "%s" changed by %s' % (key, user_email)
  email_body_params.update({
      'hostname': app_identity.get_default_version_hostname(),
      'user': user_email,
  })
  body = _NOTIFICATION_EMAIL_BODY % email_body_params
  mail.send_mail(
      sender=_SENDER_ADDRESS, to=_NOTIFICATION_ADDRESS,
      subject=subject, body=body)


def _FormatJson(obj):
  if not obj:
    return ''
  return json.dumps(obj, indent=2, sort_keys=True)

