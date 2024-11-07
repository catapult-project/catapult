# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""URI endpoint for nudging Anomaly entities and updating alert bug IDs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from httplib2 import http
import json
import logging

from google.appengine.api import users
from google.appengine.ext import ndb

from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.common import xsrf

from flask import request, make_response


@xsrf.TokenRequired
def EditAnomaliesPost():
  """Allows adding or resetting bug IDs and invalid statuses to Alerts.

    Additionally, this endpoint is also responsible for changing the start
    and end revisions of Anomaly entities.

    Request parameters:
      keys: A comma-separated list of urlsafe keys of Anomaly entities.
      bug_id: The new bug ID. This should be either the string REMOVE
          (indicating resetting the bug ID to None), or an integer. A negative
          integer indicates an invalid or ignored alert. If this is given, then
          the start and end revision ranges are ignored.
      new_start_revision: New start revision value for the alert.
      new_end_revision: New end revision value for the alert.

    Outputs:
      JSON which indicates the result. If an error has occurred, the field
      "error" should be in the result. If successful, the response is still
      expected to be JSON.
    """
  if not utils.IsValidSheriffUser():
    user = users.get_current_user()
    return request_handler.RequestHandlerReportError(
        'User "%s" not authorized.' % user, status=403)


  # Get the list of alerts to modify.
  urlsafe_keys = request.values.get('keys')
  if not urlsafe_keys:
    return make_response(
        json.dumps({'error': 'No alerts specified to add bugs to.'}))

  keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys.split(',')]
  alert_entities = ndb.get_multi(keys)

  # Get the parameters which specify the changes to make.
  bug_id = request.values.get('bug_id')
  new_start_revision = request.values.get('new_start_revision')
  new_end_revision = request.values.get('new_end_revision')
  result = None
  if bug_id:
    result = ChangeBugId(alert_entities, bug_id)
  elif new_start_revision and new_end_revision:
    result = NudgeAnomalies(alert_entities, new_start_revision,
                                 new_end_revision)
  else:
    result = {'error': 'No bug ID or new revision specified.'}
  return make_response(json.dumps(result))


def SkiaEditAnomaliesPost():
  if not utils.IsValidSheriffUser():
    logging.debug('[SkiaTriage] GetEmail: %s. TryJobUser: %s', utils.GetEmail(),
                  utils.IsTryjobUser())
    return make_response(
        json.dumps({'error': 'You must be logged in to edit anomalies.'}),
        http.HTTPStatus.UNAUTHORIZED.value)

  try:
    data = json.loads(request.data)
  except json.JSONDecodeError as e:
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)

  logging.debug('[SkiaTriage] Received edit anomalies request from Skia: %s',
                data)

  # list of anomaly keys in int
  keys = data.get('keys', [])
  if not keys:
    return make_response(
        json.dumps({'error': 'No skia anomaly keys specified to edit.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  keys = [ndb.Key('Anomaly', k) for k in keys]
  alert_entities = ndb.get_multi(keys)

  if len(alert_entities) == 0:
    logging.warning('Cannot load alert entities with keys: %s', keys)
    return make_response(
        json.dumps({'error': 'No entity loaded for editing. Keys: %s' % keys}),
        http.HTTPStatus.BAD_REQUEST.value)

  action = data.get('action', None)
  if not action:
    return make_response(
        json.dumps({'error': 'No action specified for editing.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  result = None
  if action == 'IGNORE':
    result = ChangeBugId(alert_entities, -2)
  elif action == 'RESET':
    result = ChangeBugId(alert_entities, 0)
  elif action == 'NUDGE':
    start_revision = data.get('start_revision', None)
    end_revision = data.get('end_revision', None)
    if start_revision and end_revision:
      result = NudgeAnomalies(alert_entities, start_revision, end_revision)
    else:
      result = {
          'error':
              'No valid revisions specified. %s:%s' %
              (start_revision, end_revision)
      }
  else:
    result = {'error': 'No valid action specified: %s' % (action)}
  if 'error' in result:
    return make_response(json.dumps(result), http.HTTPStatus.BAD_REQUEST.value)
  return make_response('{}')


def ChangeBugId(alert_entities, bug_id):
  """Changes or resets the bug ID of all given alerts."""
  # Change the bug ID if a new bug ID is specified and valid.
  if bug_id == 'REMOVE':
    bug_id = None
  else:
    try:
      bug_id = int(bug_id)
    except ValueError:
      return {'error': 'Invalid bug ID %s' % str(bug_id)}

  for a in alert_entities:
    a.bug_id = bug_id

  ndb.put_multi(alert_entities)

  return {'bug_id': bug_id}


def NudgeAnomalies(anomaly_entities, start, end):
  # Change the revision range if a new revision range is specified and valid.
  try:
    start = int(start)
    end = int(end)
  except ValueError:
    return {'error': 'Invalid revisions %s, %s' % (start, end)}

  for a in anomaly_entities:
    a.start_revision = start
    a.end_revision = end

  ndb.put_multi(anomaly_entities)

  return {'success': 'Alerts nudged.'}
