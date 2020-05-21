# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logic for posting Job updates to the issue tracker."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import jinja2
from collections import namedtuple
import math
import os.path

from dashboard import update_bug_with_results
from dashboard.common import utils
from dashboard.services import issue_tracker_service
from dashboard.models import histogram
from dashboard.pinpoint.models import job_state

from tracing.value.diagnostics import reserved_infos


_INFINITY = u'\u221e'
_RIGHT_ARROW = u'\u2192'


_TEMPLATE_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        searchpath=os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'templates')))
_DIFFERENCES_FOUND_TMPL = _TEMPLATE_ENV.get_template('differences_found.j2')
_CREATED_TEMPL = _TEMPLATE_ENV.get_template('job_created.j2')


class JobUpdateBuilder(object):
  """Builder for job issue updates.

  The builder lets us collect the useful information for filing an update on an
  issue, ranging from when a job is created, updated, and when it fails.

  Intended usage looks like::

    builder = JobUpdateBuilder(...)
    issue_update_info = builder.CreationUpdate()

  In cases where we encounter a failure::

    builder.AddFailure(...)
    issue_update_info = builder.FailureUpdate()
  """
  def __init__(self, job):
    self._env = {
        'url': job.url,
        'user': job.user,
        'args': job.benchmark_arguments,
        'configuration': job.configuration if job.configuration else '(None)',
    }

  def CreationUpdate(self, pending):
    env = self._env.copy()
    env.update({'pending': pending})
    comment_text = _CREATED_TEMPL.render(**env)
    return _BugUpdateInfo(comment_text, None, None, None)


class DifferencesFoundBugUpdateBuilder(object):
  """Builder for bug updates about differences found in a metric.

  Accumulate the found differences into this with AddDifference(), then call
  BuildUpdate() to get the bug update to send.

  So intended usage looks like::

    builder = DifferencesFoundBugUpdateBuilder()
    for d in FindDifferences():
      ...
      builder.AddDifference(d.commit, d.values_a, d.values_b)
    issue_update_info = builder.BuildUpdate(tags, url)
  """

  def __init__(self, metric):
    self._metric = metric
    self._differences = []
    self._examined_count = None
    self._cached_ordered_diffs_by_delta = None

  def SetExaminedCount(self, examined_count):
    self._examined_count = examined_count

  def AddDifference(self, commit, values_a, values_b):
    """Add a difference (a commit where the metric changed significantly).

    Args:
      commit: a Commit.
      values_a: (list) result values for the prior commit.
      values_b: (list) result values for this commit.
    """
    commit_info = commit.AsDict()
    self._differences.append(_Difference(commit_info, values_a, values_b))
    self._cached_ordered_diffs_by_delta = None

  def BuildUpdate(self, tags, url):
    """Return _BugUpdateInfo for the differences."""
    if len(self._differences) == 0:
      raise ValueError("BuildUpdate called with 0 differences")
    owner, cc_list, notify_why_text = self._PeopleToNotify()
    comment_text = _DIFFERENCES_FOUND_TMPL.render(
        differences=self._OrderedDifferencesByDelta(),
        url=url,
        metric=self._metric,
        notify_why_text=notify_why_text,
        doc_links=_FormatDocumentationUrls(tags),
        examined_count=self._examined_count,
    )
    labels = [
        'Pinpoint-Culprit-Found'
        if len(self._differences) == 1 else 'Pinpoint-Multiple-Culprits'
    ]
    return _BugUpdateInfo(comment_text, owner, cc_list, labels)

  def GenerateCommitCacheKey(self):
    commit_cache_key = None
    if len(self._differences) == 1:
      commit_cache_key = update_bug_with_results._GetCommitHashCacheKey(
          self._differences[0].commit_info.get('git_hash'))
    return commit_cache_key

  def _OrderedDifferencesByDelta(self):
    """Return the list of differences sorted by absolute change."""
    if self._cached_ordered_diffs_by_delta is not None:
      return self._cached_ordered_diffs_by_delta

    # First, the diffs with deltas.
    diffs_with_deltas = [(diff.MeanDelta(), diff)
                         for diff in self._differences
                         if diff.values_a and diff.values_b]
    # Followed by the remaining diffs (those with "No values" on either side),
    # in the original order.
    no_values_diffs = [diff for diff in self._differences
                       if not (diff.values_a and diff.values_b)]
    ordered_diffs = [
        diff for _, diff in sorted(
            diffs_with_deltas, key=lambda i: abs(i[0]), reverse=True)
    ] + no_values_diffs

    self._cached_ordered_diffs_by_delta = ordered_diffs
    return ordered_diffs

  def _PeopleToNotify(self):
    """Return the people to notify for these differences.

    This looks at the top commits (by absolute change), and returns a tuple of:
      * owner (str, will be ignored if the bug is already assigned)
      * cc_list (list, authors of the top 2 commits)
      * why_text (str, text explaining why this owner was chosen)
    """
    ordered_commits = [
        diff.commit_info for diff in self._OrderedDifferencesByDelta()
    ]

    # CC the folks in the top N commits.  N is scaled by the number of commits
    # (fewer than 10 means N=1, fewer than 100 means N=2, etc.)
    commits_cap = int(math.floor(math.log10(len(ordered_commits)))) + 1
    cc_list = set()
    for commit in ordered_commits[:commits_cap]:
      cc_list.add(commit['author'])

    # Assign to the author of the top commit.  If that is an autoroll, assign to
    # a sheriff instead.
    why_text = ''
    top_commit = ordered_commits[0]
    owner = top_commit['author']
    sheriff = utils.GetSheriffForAutorollCommit(owner, top_commit['message'])
    if sheriff:
      owner = sheriff
      why_text = 'Assigning to sheriff %s because "%s" is a roll.' % (
          sheriff, top_commit['subject'])

    return owner, cc_list, why_text


class _Difference(object):

  def __init__(self, commit_info, values_a, values_b):
    self.commit_info = commit_info
    self.values_a = values_a
    self.values_b = values_b

  def MeanDelta(self):
    return job_state.Mean(self.values_b) - job_state.Mean(self.values_a)

  def Formatted(self):
    if self.values_a:
      mean_a = job_state.Mean(self.values_a)
      formatted_a = '%.4g' % mean_a
    else:
      mean_a = None
      formatted_a = 'No values'

    if self.values_b:
      mean_b = job_state.Mean(self.values_b)
      formatted_b = '%.4g' % mean_b
    else:
      mean_b = None
      formatted_b = 'No values'

    difference = ''
    if self.values_a and self.values_b:
      difference = ' (%+.4g)' % (mean_b - mean_a)
      if mean_a:
        difference += ' (%+.4g%%)' % ((mean_b - mean_a) / mean_a * 100)
      else:
        difference += ' (+%s%%)' % _INFINITY
    return '%s %s %s%s' % (formatted_a, _RIGHT_ARROW, formatted_b, difference)


class _BugUpdateInfo(
    namedtuple('_BugUpdateInfo',
               ['comment_text', 'owner', 'cc_list', 'labels'])):
  """An update to post to a bug.

  This is the return type of DifferencesFoundBugUpdateBuilder.BuildUpdate.
  """


def _ComputePostMergeDetails(issue_tracker, commit_cache_key, cc_list):
  merge_details = {}
  if commit_cache_key:
    merge_details = update_bug_with_results.GetMergeIssueDetails(
        issue_tracker, commit_cache_key)
    if merge_details['id']:
      cc_list = []
  return merge_details, cc_list


def _GetBugStatus(issue_tracker, bug_id, project='chromium'):
  if not bug_id:
    return None

  issue_data = issue_tracker.GetIssue(bug_id, project=project)
  if not issue_data:
    return None

  return issue_data.get('status')


def _FormatDocumentationUrls(tags):
  if not tags:
    return ''

  # TODO(simonhatch): Tags isn't the best way to get at this, but wait until
  # we move this back into the dashboard so we have a better way of getting
  # at the test path.
  # crbug.com/876899
  test_path = tags.get('test_path')
  if not test_path:
    return ''

  test_suite = utils.TestKey('/'.join(test_path.split('/')[:3]))
  docs = histogram.SparseDiagnostic.GetMostRecentDataByNamesSync(
      test_suite, [reserved_infos.DOCUMENTATION_URLS.name])

  if not docs:
    return ''

  docs = docs[reserved_infos.DOCUMENTATION_URLS.name].get('values')
  footer = '\n\n%s:\n  %s' % (docs[0][0], docs[0][1])
  return footer


def UpdatePostAndMergeDeferred(bug_update_builder, bug_id, tags, url, project):
  if not bug_id:
    return
  commit_cache_key = bug_update_builder.GenerateCommitCacheKey()
  bug_update = bug_update_builder.BuildUpdate(tags, url)
  issue_tracker = issue_tracker_service.IssueTrackerService(
      utils.ServiceAccountHttp())
  merge_details, cc_list = _ComputePostMergeDetails(issue_tracker,
                                                    commit_cache_key,
                                                    bug_update.cc_list)
  current_bug_status = _GetBugStatus(issue_tracker, bug_id, project=project)
  if not current_bug_status:
    return

  status = None
  bug_owner = None

  if current_bug_status in ['Untriaged', 'Unconfirmed', 'Available']:
    # Set the bug status and owner if this bug is opened and unowned.
    status = 'Assigned'
    bug_owner = bug_update.owner

  issue_tracker.AddBugComment(
      bug_id,
      bug_update.comment_text,
      status=status,
      cc_list=sorted(cc_list),
      owner=bug_owner,
      labels=bug_update.labels,
      merge_issue=merge_details.get('id'),
      project=project)
  update_bug_with_results.UpdateMergeIssue(
      commit_cache_key, merge_details, bug_id, project=project)
