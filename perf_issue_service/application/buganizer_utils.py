# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helpers for handling Buganizer migration.

Monorail is being deprecated and replaced by Buganizer in 2024. Migration
happens by projects. Chromeperf needs to support both Monorail and Buganizer
during the migration until the last project we supported is fully migrated.

Before the first migration happens, we will keep the consumers untouched
in the Monorail fashion. The requests and responses to and from Buganizer will
be reconciled to the Monorail format on perf_issue_service.
"""

import logging

# ============ mapping helpers start ============
# The mapping here are for ad hoc testing. The real mappings will be different
# from project to project and will be added in future CLs.

def FindBuganizerComponentId(monorail_component):
  # temp. will have real mapping.
  del monorail_component
  return 1325852

def FindBuganizerComponents(monorail_project_name):
  """return a list of components in buganizer based on the monorail project

  The current implementation is ad hoc as the component mappings are not
  fully set up on buganizer yet.
  """
  if monorail_project_name == 'MigratedProject':
    return ['1325852']
  return []

def FindMonorailProject(buganizer_component_id):
  if buganizer_component_id == '1325852':
    return 'MigratedProject'
  return ''


def FindBuganizerHotlists(monorail_labels):
  hotlists = []
  for label in monorail_labels:
    hotlist = _FindBuganizerHotlist(label)
    if hotlist:
      hotlists.append(hotlist)
  logging.debug(
    '[PerfIssueService] labels (%s) -> hotlists (%s)',
    monorail_labels, hotlists)
  return hotlists


def _FindBuganizerHotlist(monorail_label):
  if monorail_label == 'chromeperf-test':
    return '5141966'
  elif monorail_label == 'chromeperf-test-2':
    return '5142065'
  return None


def _FindMonorailLabel(buganizer_hotlist):
  if buganizer_hotlist == '5141966':
    return 'chromeperf-test'
  elif buganizer_hotlist == '5142065':
    return 'chromeperf-test-2'
  return None


def _FindMonorailStatus(buganizer_status):
  if buganizer_status == 'NEW':
    return 'Unconfirmed'
  elif buganizer_status == 'ASSIGNED':
    return "Assigned"
  elif buganizer_status == 'ACCEPTED':
    return 'Started'
  elif buganizer_status == 'FIXED':
    return 'Fixed'
  elif buganizer_status == 'VERIFIED':
    return 'Verified'
  return 'Untriaged'


def FindBuganizerStatus(monorail_status):
  if monorail_status == 'Unconfirmed':
    return 'NEW'
  elif monorail_status == 'Assigned':
    return "ASSIGNED"
  elif monorail_status == 'Started':
    return 'ACCEPTED'
  elif monorail_status == 'Fixed':
    return 'FIXED'
  elif monorail_status == 'Verified':
    return 'VERIFIED'
  return 'STATUS_UNSPECIFIED'

# ============ mapping helpers end ============

def GetBuganizerStatusUpdate(issue_update, status_enum):
  ''' Get the status from an issue update

  In Buganizer, each update event is saved in an issueUpdate struct like:
    {
      "author": {
        "emailAddress": "wenbinzhang@google.com"
      },
      "timestamp": "2023-07-28T22: 17: 34.721Z",
      ...
      "fieldUpdates": [
        {
          "field": "status",
          "singleValueUpdate": {
            "oldValue": {
              "@type": "type.googleapis.com/google.protobuf.Int32Value",
              "value": 2
            },
            "newValue": {
              "@type": "type.googleapis.com/google.protobuf.Int32Value",
              "value": 4
            }
          }
        }
      ],
      ...
      "version": 5,
      "issueId": "285172796"
    }
  Noticed that each update on the UI can have multiple operations, but each of
  operations is a single issue update. So far we only use the 'status' value,
  thus the other updates like priority change are not returned here.
  '''
  for field_update in issue_update.get('fieldUpdates', []):
    if field_update.get('field') == 'status':
      new_status = field_update.get('singleValueUpdate').get('newValue').get('value')

      # The current status returned from issueUpdate is integer, which is
      # different from the definition in the discovery doc.
      # I'm using  service._schema.get() to load the schema in JSON.
      if isinstance(new_status, int):
        new_status = status_enum[new_status]

      status_update = {
        'status': _FindMonorailStatus(new_status)
      }
      return status_update
  return None


def LoadPriorityFromMonorailLabels(monorail_labels):
  ''' Load the priority from monorail labels if it is set

  In Monorail, a label like 'Pri-X' is used set the issue's priority to X.
  X can be range from 0 to 4. Currently Monorail scan the labels in order
  and set the priority as it sees any. Thus, the last X will be kept. Here
  we changed the logic to keep the highest level (lowest value.)

  Args:
    monorail_labels: a list of labels in monorail fashion.

  Returns:
    the priority from the label if any, otherwise 2 by default.
  '''
  priority = 99
  for label in monorail_labels:
    if label.startswith('Pri-'):
      label_priority = int(label[4])
      priority = min(priority, label_priority)
  if priority == 99:
    return 2
  return priority


def ReconcileBuganizerIssue(buganizer_issue):
  '''Reconcile a Buganizer issue into the Monorail format

  During the Buganizer migration, we try to minimize the changes on the
  consumers of the issues. Thus, we will reconcile the results into the
  exising Monorail format before returning the results.
  '''
  monorail_issue = {}
  issue_state = buganizer_issue.get('issueState')

  monorail_issue['projectId'] = FindMonorailProject(issue_state['componentId'])

  monorail_issue['id'] = buganizer_issue['issueId']

  buganizer_status = issue_state['status']
  if buganizer_status in ('NEW', 'ASSIGNED', 'ACCEPTED'):
    monorail_issue['state'] = 'open'
  else:
    monorail_issue['state'] = 'closed'

  monorail_issue['status'] = _FindMonorailStatus(buganizer_status)

  monorail_author = {
    'name': issue_state['reporter']
  }
  monorail_issue['author'] = monorail_author

  monorail_issue['summary'] = issue_state['title']

  monorail_issue['owner'] = issue_state.get('assignee', None)

  hotlist_ids = buganizer_issue.get('hotlistIds', [])
  label_names = [_FindMonorailLabel(hotlist_id) for hotlist_id in hotlist_ids]
  monorail_issue['labels'] = [label for label in label_names if label]

  return monorail_issue
