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


def FindBuganizerComponents(monorail_project_name):
  """return a list of components in buganizer based on the monorail project

  The current implementation is ad hoc as the component mappings are not
  fully set up on buganizer yet.
  """
  if monorail_project_name == 'MigratedProject':
    return ['1325852']
  return []

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