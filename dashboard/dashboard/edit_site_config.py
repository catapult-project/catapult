# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for adding and editing sheriff rotations."""

import difflib
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

Key: %(key)s

Non-namespaced value diff:
%(value_diff)s

Externally-visible value diff:
%(external_value_diff)s

Internal-only value diff:
%(internal_value_diff)s
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
      self.RenderHtml('edit_site_config.html', template_params)
      return

    _SendNotificationEmail(template_params)
    self.RenderHtml('edit_site_config.html', template_params)


def _SendNotificationEmail(template_params):
  user_email = users.get_current_user().email()
  subject = 'Config "%s" changed by %s' % (
      template_params['key'], user_email)
  mail.send_mail(
      sender=_SENDER_ADDRESS,
      to=_NOTIFICATION_ADDRESS,
      subject=subject,
      body=_NotificationEmailBody(template_params))


def _NotificationEmailBody(template_params):
  key = template_params['key']
  value = template_params['value']
  external_value = template_params['external_value']
  internal_value = template_params['internal_value']
  return _NOTIFICATION_EMAIL_BODY % {
      'key': key,
      'value_diff': _DiffJson(
          stored_object.Get(key),
          json.loads(value) if value else None),
      'external_value_diff': _DiffJson(
          namespaced_stored_object.Get(key),
          json.loads(external_value) if external_value else None),
      'internal_value_diff': _DiffJson(
          namespaced_stored_object.GetExternal(key),
          json.loads(internal_value) if internal_value else None),
      'hostname': app_identity.get_default_version_hostname(),
      'user': users.get_current_user().email(),
  }


def _DiffJson(obj1, obj2):
  """Returns a string diff of two JSON-serializable objects."""
  differ = difflib.Differ()
  return '\n'.join(differ.compare(
      _FormatJson(obj1).splitlines(),
      _FormatJson(obj2).splitlines()))


def _FormatJson(obj):
  if not obj:
    return ''
  return json.dumps(obj, indent=2, sort_keys=True)
