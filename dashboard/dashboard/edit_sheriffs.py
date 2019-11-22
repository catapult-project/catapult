# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for adding and editing sheriff rotations."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard import edit_config_handler
from dashboard.models import sheriff
from dashboard import sheriff_pb2
from google.protobuf import text_format


class EditSheriffsHandler(edit_config_handler.EditConfigHandler):
  """Handles editing of Sheriff entities.

  The post method is inherited from EditConfigHandler. It takes the request
  parameters documented there, as well as the following parameters, which
  are properties of Sheriff:
    url: A URL at which there is a list of email addresses to send mail to.
    email: An email address to send mail to, possibly a mailing list.
    internal-only: Whether the data should be considered internal-only.
    summarize: Whether to send emails in a summary form.
  """

  def __init__(self, request, response):
    super(EditSheriffsHandler, self).__init__(
        request, response, sheriff.Sheriff)

  def get(self):
    """Renders the UI with the form."""
    def SheriffData(sheriff_entity):
      subscription = sheriff_pb2.Subscription()
      subscription.name = sheriff_entity.key.string_id()
      subscription.rotation_url = sheriff_entity.url or ''
      subscription.notification_email = sheriff_entity.email or ''
      if not sheriff_entity.internal_only:
        subscription.visibility = sheriff_pb2.Subscription.PUBLIC

      # Find the labels, and find the ones that say 'Component-' and turn those
      # into components, formatting appropriately.
      for label in sorted(sheriff_entity.labels):
        if label.startswith('Component-'):
          subscription.bug_components.append('>'.join(label.split('-')[1:]))
        else:
          subscription.bug_labels.append(label)

      # Treat all patterns as globs for now.
      for pattern in sorted(sheriff_entity.patterns):
        p = subscription.patterns.add()
        p.glob = pattern

      return {
          'url': sheriff_entity.url or '',
          'email': sheriff_entity.email or '',
          'patterns': '\n'.join(sorted(sheriff_entity.patterns)),
          'labels': ','.join(sorted(sheriff_entity.labels)),
          'internal_only': sheriff_entity.internal_only,
          'summarize': sheriff_entity.summarize,
          'subscription': text_format.MessageToString(subscription)
      }

    sheriff_dicts = {entity.key.string_id(): SheriffData(entity)
                     for entity in sheriff.Sheriff.query()}

    self.RenderHtml('edit_sheriffs.html', {
        'sheriffs_json': json.dumps(sheriff_dicts),
        'sheriff_names': sorted(sheriff_dicts),
    })

  def _UpdateFromRequestParameters(self, sheriff_entity):
    """Updates the given Sheriff based on query parameters.

    Args:
      sheriff_entity: A Sheriff entity.
    """
    # This overrides the method in the superclass.
    sheriff_entity.url = self.request.get('url') or None
    sheriff_entity.email = self.request.get('email') or None
    sheriff_entity.internal_only = self.request.get('internal-only') == 'true'
    labels = self.request.get('labels')
    if labels:
      sheriff_entity.labels = labels.split(',')
    else:
      sheriff_entity.labels = []
    sheriff_entity.summarize = self.request.get('summarize') == 'true'
