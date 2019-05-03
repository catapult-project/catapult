# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to update bugs after bisects."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from google.appengine.ext import ndb

from dashboard.common import layered_cache
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.services import issue_tracker_service


_COMMIT_HASH_CACHE_KEY = 'commit_hash_%s'

_NOT_DUPLICATE_MULTIPLE_BUGS_MSG = """
Possible duplicate of crbug.com/%s, but not merging issues due to multiple
culprits in destination issue.
"""


def GetMergeIssueDetails(issue_tracker, commit_cache_key):
  """Get's the issue this one might be merged into.

  Returns: A dict with the following fields:
    issue: The issue details from the issue tracker service.
    id: The id of the issue we should merge into. This may be set to None if
        either there is no other bug with this culprit, or we shouldn't try to
        merge into that bug.
    comments: Additional comments to add to the bug.
  """
  merge_issue_key = layered_cache.GetExternal(commit_cache_key)
  if not merge_issue_key:
    return {'issue': {}, 'id': None, 'comments': ''}

  merge_issue = issue_tracker.GetIssue(merge_issue_key)
  if not merge_issue:
    return {'issue': {}, 'id': None, 'comments': ''}

  # Check if we can duplicate this issue against an existing issue.
  merge_issue_id = None
  additional_comments = ""

  # We won't duplicate against an issue that itself is already
  # a duplicate though. Could follow the whole chain through but we'll
  # just keep things simple and flat for now.
  if merge_issue.get('status') != issue_tracker_service.STATUS_DUPLICATE:
    merge_issue_id = str(merge_issue.get('id'))

  return {
      'issue': merge_issue,
      'id': merge_issue_id,
      'comments': additional_comments
  }


def UpdateMergeIssue(commit_cache_key, merge_details, bug_id):
  if not merge_details:
    return

  # If the issue we were going to merge into was itself a duplicate, we don't
  # dup against it but we also don't merge existing anomalies to it or cache it.
  if merge_details['issue'].get('status') == (
      issue_tracker_service.STATUS_DUPLICATE):
    return

  _MapAnomaliesAndUpdateBug(merge_details['id'], bug_id)
  _UpdateCacheKeyForIssue(merge_details['id'], commit_cache_key, bug_id)


def _MapAnomaliesAndUpdateBug(merge_issue_id, bug_id):
  if merge_issue_id:
    _MapAnomaliesToMergeIntoBug(merge_issue_id, bug_id)
    # Mark the duplicate bug's Bug entity status as closed so that
    # it doesn't get auto triaged.
    bug = ndb.Key('Bug', bug_id).get()
    if bug:
      bug.status = bug_data.BUG_STATUS_CLOSED
      bug.put()


def _UpdateCacheKeyForIssue(merge_issue_id, commit_cache_key, bug_id):
  # Cache the commit info and bug ID to datastore when there is no duplicate
  # issue that this issue is getting merged into. This has to be done only
  # after the issue is updated successfully with bisect information.
  if commit_cache_key and not merge_issue_id:
    layered_cache.SetExternal(commit_cache_key, str(bug_id),
                              days_to_keep=30)
    logging.info('Cached bug id %s and commit info %s in the datastore.',
                 bug_id, commit_cache_key)


def _MapAnomaliesToMergeIntoBug(dest_bug_id, source_bug_id):
  """Maps anomalies from source bug to destination bug.

  Args:
    dest_bug_id: Merge into bug (base bug) number.
    source_bug_id: The bug to be merged.
  """
  anomalies, _, _ = anomaly.Anomaly.QueryAsync(
      bug_id=source_bug_id).get_result()

  bug_id = int(dest_bug_id)
  for a in anomalies:
    a.bug_id = bug_id

  ndb.put_multi(anomalies)


def _GetCommitHashCacheKey(git_hash):
  """Gets a commit hash cache key for the given bisect results output.

  Args:
    results_data: Bisect results data.

  Returns:
    A string to use as a layered_cache key, or None if we don't want
    to merge any bugs based on this bisect result.
  """
  if not git_hash:
    return None
  return _COMMIT_HASH_CACHE_KEY % git_hash
