# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from flask import make_response, Blueprint, request
import logging

from models import alert_group

alert_groups = Blueprint('alert_groups', __name__)


@alert_groups.route('/<group_id>/duplicates', methods=['GET'])
def FindDuplicatesHandler(group_id):
  duplicate_keys = alert_group.AlertGroup.FindDuplicates(group_id)

  return make_response(duplicate_keys)


@alert_groups.route('/<current_group_key>/canonical/issue_id/<issue_id>/project_name/<project_name>', methods=['GET'])
def FindCanonicalGroupHandler(current_group_key, issue_id, project_name):
  canonical_group = alert_group.AlertGroup.FindCanonicalGroupByIssue(current_group_key, int(issue_id), project_name)

  if canonical_group:
    return make_response(canonical_group)
  return make_response('')


@alert_groups.route('/<group_id>/anomalies', methods=['GET'])
def GetAnomaliesHandler(group_id):
  try:
    group_id = int(group_id)
  except ValueError:
    logging.debug('Using group id %s as string.', group_id)

  try:
    anomalies = alert_group.AlertGroup.GetAnomaliesByID(group_id)
  except alert_group.NoEntityFoundException as e:
    return make_response(str(e), 404)
  return make_response(anomalies)


@alert_groups.route('/test/<path:test_key>/start/<start_rev>/end/<end_rev>', methods=['GET'])
def GetGroupsForAnomalyHandler(test_key, start_rev, end_rev):
  try:
    group_keys = alert_group.AlertGroup.GetGroupsForAnomaly(
      test_key, start_rev, end_rev)
  except alert_group.SheriffConfigRequestException as e:
    return make_response(str(e), 500)

  return make_response(group_keys)

@alert_groups.route('/all', methods=['GET'])
def GetAllActiveGroups():
  all_group_keys = alert_group.AlertGroup.GetAll()

  return make_response(all_group_keys)


@alert_groups.route('/ungrouped', methods=['GET'])
def PostUngroupedGroupsHandler():
  alert_group.AlertGroup.ProcessUngroupedAlerts()

  return make_response('')