# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The workflow to manipulate an AlertGroup.

We want to separate the workflow from data model. So workflow
is used to implement all AlertGroup's state transitions.

A typical workflow includes these steps:
- Associate anomalies to an AlertGroup
- Update related issues
- Trigger auto-triage if necessary
- Trigger auto-bisection if necessary
- Manage an AlertGroup's lifecycle

`AlertGroupWorkflow(group).Process()` is enough for most of use cases.
But it provides the ability to mock any input and any service, which makes
testing easier and we can have a more predictable behaviour.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import datetime
import itertools
import jinja2
import logging
import os

from google.appengine.ext import ndb

from dashboard import pinpoint_request
from dashboard import sheriff_config_client
from dashboard import revision_info_client
from dashboard.common import file_bug
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import subscription
from dashboard.services import crrev_service
from dashboard.services import gitiles_service
from dashboard.services import issue_tracker_service
from dashboard.services import pinpoint_service

# Templates used for rendering issue contents
_TEMPLATE_LOADER = jinja2.FileSystemLoader(
    searchpath=os.path.join(os.path.dirname(os.path.realpath(__file__))))
_TEMPLATE_ENV = jinja2.Environment(loader=_TEMPLATE_LOADER)
_TEMPLATE_ISSUE_TITLE = jinja2.Template(
    '[{{ group.subscription_name }}]: '
    '{{ regressions|length }} regressions in {{ group.name }}')
_TEMPLATE_ISSUE_CONTENT = _TEMPLATE_ENV.get_template(
    'alert_groups_bug_description.j2')
_TEMPLATE_ISSUE_COMMENT = _TEMPLATE_ENV.get_template(
    'alert_groups_bug_comment.j2')
_TEMPLATE_REOPEN_COMMENT = _TEMPLATE_ENV.get_template('reopen_issue_comment.j2')
_TEMPLATE_AUTO_BISECT_COMMENT = _TEMPLATE_ENV.get_template(
    'auto_bisect_comment.j2')
_TEMPLATE_GROUP_WAS_MERGED = _TEMPLATE_ENV.get_template(
    'alert_groups_merge_bug_comment.j2')

# Waiting 7 days to gather more potential alerts. Just choose a long
# enough time and all alerts arrive after archived shouldn't be silent
# merged.
_ALERT_GROUP_ACTIVE_WINDOW = datetime.timedelta(days=7)

# (2020-05-01) Only ~62% issues' alerts are triggered in one hour.
# But we don't want to wait all these long tail alerts finished.
# 20 minutes are enough for a single bot.
#
# SELECT APPROX_QUANTILES(diff, 100) as percentiles
# FROM (
#   SELECT TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), MINUTE) as diff
#   FROM chromeperf.chromeperf_dashboard_data.anomalies
#   WHERE 'Chromium Perf Sheriff' IN UNNEST(subscription_names)
#         AND bug_id IS NOT NULL AND timestamp > '2020-03-01'
#   GROUP BY bug_id
# )
_ALERT_GROUP_TRIAGE_DELAY = datetime.timedelta(minutes=20)

# The score is based on overall 60% reproduction rate of pinpoint bisection.
_ALERT_GROUP_DEFAULT_SIGNAL_QUALITY_SCORE = 0.6


class SignalQualityScore(ndb.Model):
  score = ndb.FloatProperty()
  updated_time = ndb.DateTimeProperty()


class InvalidPinpointRequest(Exception):
  pass


class AlertGroupWorkflow(object):
  """Workflow used to manipulate the AlertGroup.

  Workflow will assume the group passed from caller is same as the group in
  datastore. It may update the group in datastore multiple times during the
  process.
  """

  class Config(
      collections.namedtuple('WorkflowConfig',
                             ('active_window', 'triage_delay'))):
    __slots__ = ()

  class GroupUpdate(
      collections.namedtuple('GroupUpdate',
                             ('now', 'anomalies', 'issue', 'canonical_group'))):
    __slots__ = ()

    def __new__(cls, now, anomalies, issue, canonical_group=None):
      return super(AlertGroupWorkflow.GroupUpdate,
                   cls).__new__(cls, now, anomalies, issue, canonical_group)

  class BenchmarkDetails(
      collections.namedtuple('BenchmarkDetails',
                             ('name', 'owners', 'regressions', 'info_blurb'))):
    __slots__ = ()

  class BugUpdateDetails(
      collections.namedtuple('BugUpdateDetails',
                             ('components', 'cc', 'labels'))):
    __slots__ = ()

  def __init__(
      self,
      group,
      config=None,
      sheriff_config=None,
      issue_tracker=None,
      pinpoint=None,
      crrev=None,
      gitiles=None,
      revision_info=None,
      service_account=None,
  ):
    self._group = group
    self._config = config or self.Config(
        active_window=_ALERT_GROUP_ACTIVE_WINDOW,
        triage_delay=_ALERT_GROUP_TRIAGE_DELAY,
    )
    self._sheriff_config = (
        sheriff_config or sheriff_config_client.GetSheriffConfigClient())
    self._issue_tracker = issue_tracker or _IssueTracker()
    self._pinpoint = pinpoint or pinpoint_service
    self._crrev = crrev or crrev_service
    self._gitiles = gitiles or gitiles_service
    self._revision_info = revision_info or revision_info_client
    self._service_account = service_account or utils.ServiceAccountEmail

  def _FindCanonicalGroup(self, issue):
    """Finds the canonical issue group if any.

    Args:
      issue: Monorail API issue json. If the issue has any comments the json
        should contain additional 'comments' key with the list of Monorail API
        comments jsons.

    Returns:
      AlertGroup object or None if the issue is not duplicate, canonical issue
      has no corresponding group or duplicate chain forms a loop.
    """
    if issue.get('status') != issue_tracker_service.STATUS_DUPLICATE:
      return None

    merged_into = None
    latest_id = 0
    for comment in issue.get('comments', []):
      if comment['updates'].get('mergedInto') and comment['id'] >= latest_id:
        merged_into = int(comment['updates'].get('mergedInto'))
        latest_id = comment['id']
    if not merged_into:
      return None
    logging.info('Found canonical issue for the groups\' issue: %d',
                 merged_into)

    query = alert_group.AlertGroup.query(
        alert_group.AlertGroup.active == True,
        # It is impossible to merge bugs from different projects in monorail.
        # So the canonical group bug is guarandeed to have the same project.
        alert_group.AlertGroup.bug.project == self._group.bug.project,
        alert_group.AlertGroup.bug.bug_id == merged_into)
    query_result = query.fetch(limit=1)
    if not query_result:
      return None

    canonical_group = query_result[0]
    visited = set()
    while canonical_group.canonical_group:
      visited.add(canonical_group.key)
      next_group_key = canonical_group.canonical_group
      # Visited check is just precaution.
      # If it is true - the system previously failed to prevent loop creation.
      if next_group_key == self._group.key or next_group_key in visited:
        logging.warning(
            'Alert group auto merge failed. Found a loop while '
            'searching for a canonical group for %r', self._group)
        return None
      canonical_group = next_group_key.get()

    logging.info('Found canonical group: %s', canonical_group.key.string_id())
    return canonical_group

  def _FindDuplicateGroups(self):
    query = alert_group.AlertGroup.query(
        alert_group.AlertGroup.active == True,
        alert_group.AlertGroup.canonical_group == self._group.key)
    return query.fetch()

  def _FindRelatedAnomalies(self, groups):
    query = anomaly.Anomaly.query(
        anomaly.Anomaly.groups.IN([g.key for g in groups]))
    return query.fetch()

  def _PrepareGroupUpdate(self):
    """Prepares default input for the workflow Process

    Returns:
      GroupUpdate object that contains list of related anomalies,
      Monorail API issue json and canonical AlertGroup if any.
    """
    duplicate_groups = self._FindDuplicateGroups()
    anomalies = self._FindRelatedAnomalies([self._group] + duplicate_groups)
    now = datetime.datetime.utcnow()
    issue = None
    canonical_group = None
    if self._group.status in {
        self._group.Status.triaged, self._group.Status.bisected,
        self._group.Status.closed
    }:
      issue = self._issue_tracker.GetIssue(
          self._group.bug.bug_id, project=self._group.bug.project)
      # GetIssueComments doesn't work with empty project id so we have to
      # manually replace it with 'chromium'.
      issue['comments'] = self._issue_tracker.GetIssueComments(
          self._group.bug.bug_id, project=self._group.bug.project or 'chromium')
      canonical_group = self._FindCanonicalGroup(issue)
    return self.GroupUpdate(now, anomalies, issue, canonical_group)

  def Process(self, update=None):
    """Process the workflow.

    The workflow promises to only depend on the provided update and injected
    dependencies. The workflow steps will always be reproducible if all the
    inputs are the same.

    Process will always update the group and store once the steps have
    completed.

    The update argument can be a prepared GroupUpdate instance or None (if
    None, then Process will prepare the update itself).

    Returns the key for the associated group when the workflow was
    initialized."""

    logging.info('Processing workflow for group %s', self._group.key)
    update = update or self._PrepareGroupUpdate()
    logging.info('%d anomalies', len(update.anomalies))

    # TODO(crbug.com/1240370): understand why Datastore query may return empty
    # anomalies list.
    if (not update.anomalies and self._group.anomalies
        and self._group.group_type != alert_group.AlertGroup.Type.reserved):
      logging.error('No anomailes detected. Skipping this run.')
      return self._group.key

    # Process input before we start processing the group.
    for a in update.anomalies:
      subscriptions, _ = self._sheriff_config.Match(
          a.test.string_id(), check=True)
      a.subscriptions = subscriptions
      matching_subs = [
          s for s in subscriptions if s.name == self._group.subscription_name
      ]
      a.auto_triage_enable = any(s.auto_triage_enable for s in matching_subs)
      if a.auto_triage_enable:
        logging.info('auto_triage_enable for %s due to subscription: %s',
                     a.test.string_id(),
                     [s.name for s in matching_subs if s.auto_triage_enable])

      a.auto_merge_enable = any(s.auto_merge_enable for s in matching_subs)

      if a.auto_merge_enable:
        logging.info('auto_merge_enable for %s due to subscription: %s',
                     a.test.string_id(),
                     [s.name for s in matching_subs if s.auto_merge_enable])

      a.auto_bisect_enable = any(s.auto_bisect_enable for s in matching_subs)
      a.relative_delta = (
          abs(a.absolute_delta / float(a.median_before_anomaly))
          if a.median_before_anomaly != 0. else float('Inf'))

    added = self._UpdateAnomalies(update.anomalies)

    if update.issue:
      group_merged = self._UpdateCanonicalGroup(update.anomalies,
                                                update.canonical_group)
      self._UpdateStatus(update.issue)
      self._UpdateAnomaliesIssues(update.anomalies, update.canonical_group)

      # Current group is a duplicate.
      if self._group.canonical_group is not None:
        if group_merged:
          logging.info('Merged group %s into group %s',
                       self._group.key.string_id(),
                       update.canonical_group.key.string_id())
          self._FileDuplicatedNotification(update.canonical_group)
        self._UpdateDuplicateIssue(update.anomalies, added)
        assert (self._group.status == self._group.Status.closed), (
            'The issue is closed as duplicate (\'state\' is \'closed\'). '
            'However the groups\' status doesn\'t match the issue status')

      elif self._UpdateIssue(update.issue, update.anomalies, added):
        # Only operate on alert group if nothing updated to prevent flooding
        # monorail if some operations keep failing.
        return self._CommitGroup()

    group = self._group
    if group.updated + self._config.active_window <= update.now:
      self._Archive()
    elif group.created + self._config.triage_delay <= update.now and (
        group.status in {group.Status.untriaged}):
      logging.info('created: %s, triage_delay: %s", now: %s, status: %s',
                   group.created, self._config.triage_delay, update.now,
                   group.status)
      self._TryTriage(update.now, update.anomalies)
    elif group.status in {group.Status.triaged}:
      self._TryBisect(update)
    return self._CommitGroup()

  def _CommitGroup(self):
    return self._group.put()

  def _UpdateAnomalies(self, anomalies):
    added = [a for a in anomalies if a.key not in self._group.anomalies]
    self._group.anomalies = [a.key for a in anomalies]
    return added

  def _UpdateStatus(self, issue):
    if issue.get('state') == 'closed':
      self._group.status = self._group.Status.closed
    elif self._group.status == self._group.Status.closed:
      self._group.status = self._group.Status.triaged

  def _UpdateCanonicalGroup(self, anomalies, canonical_group):
    # If canonical_group is None, self._group will be separated from its'
    # canonical group. Since we only rely on _group.canonical_group for
    # determining duplicate status, setting canonical_group to None will
    # separate the groups. Anomalies that were added to the canonical group
    # during merged perios can't be removed.
    if canonical_group is None:
      self._group.canonical_group = None
      return False
    # Only merge groups if there is at least one anomaly that allows merge.
    if (self._group.canonical_group != canonical_group.key
        and any(a.auto_merge_enable for a in anomalies)):
      self._group.canonical_group = canonical_group.key
      return True
    return False

  def _UpdateAnomaliesIssues(self, anomalies, canonical_group):
    for a in anomalies:
      if not a.auto_triage_enable:
        continue
      if canonical_group is not None and a.auto_merge_enable:
        a.project_id = canonical_group.project_id
        a.bug_id = canonical_group.bug.bug_id
      elif a.bug_id is None:
        a.project_id = self._group.project_id
        a.bug_id = self._group.bug.bug_id

    # Write back bug_id to anomalies. We can't do it when anomaly is
    # found because group may be updating at the same time.
    ndb.put_multi(anomalies)

  def _UpdateIssue(self, issue, anomalies, added):
    """Update the status of the monorail issue.

    Returns True if the issue was changed.
    """
    # Check whether all the anomalies associated have been marked recovered.
    if all(a.recovered for a in anomalies if not a.is_improvement):
      if issue.get('state') == 'open':
        self._CloseBecauseRecovered()
      return True

    new_regressions, subscriptions = self._GetRegressions(added)
    all_regressions, _ = self._GetRegressions(anomalies)

    # Only update issue if there is at least one regression
    if not new_regressions:
      return False

    closed_by_pinpoint = False
    for c in sorted(
        issue.get('comments') or [], key=lambda c: c["id"], reverse=True):
      if c.get('updates', {}).get('status') in ('WontFix', 'Fixed', 'Verified',
                                                'Invalid', 'Duplicate', 'Done'):
        closed_by_pinpoint = (c.get('author') == self._service_account())
        break

    has_new_regression = any(a.auto_bisect_enable
                             for a in anomalies
                             if not a.is_improvement and not a.recovered)

    if (issue.get('state') == 'closed' and closed_by_pinpoint
        and has_new_regression):
      self._ReopenWithNewRegressions(all_regressions, new_regressions,
                                     subscriptions)
    else:
      self._FileNormalUpdate(all_regressions, new_regressions, subscriptions)
    return True

  def _UpdateDuplicateIssue(self, anomalies, added):
    new_regressions, subscriptions = self._GetRegressions(added)
    all_regressions, _ = self._GetRegressions(anomalies)

    # Only update issue if there is at least one regression
    if not new_regressions:
      return False

    self._FileNormalUpdate(
        all_regressions,
        new_regressions,
        subscriptions,
        new_regression_notification=False)

  def _CloseBecauseRecovered(self):
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        'All regressions for this issue have been marked recovered; closing.',
        status='WontFix',
        labels='Chromeperf-Auto-Closed',
        project=self._group.project_id,
        send_email=False,
    )

  def _ReopenWithNewRegressions(self, all_regressions, added, subscriptions):
    summary = _TEMPLATE_ISSUE_TITLE.render(
        self._GetTemplateArgs(all_regressions))
    comment = _TEMPLATE_REOPEN_COMMENT.render(self._GetTemplateArgs(added))
    components, cc, _ = self._ComputeBugUpdate(subscriptions, added)
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        comment,
        summary=summary,
        components=components,
        labels=['Chromeperf-Auto-Reopened'],
        status='Unconfirmed',
        cc_list=cc,
        project=self._group.project_id,
        send_email=False,
    )

  def _FileNormalUpdate(self,
                        all_regressions,
                        added,
                        subscriptions,
                        new_regression_notification=True):
    summary = _TEMPLATE_ISSUE_TITLE.render(
        self._GetTemplateArgs(all_regressions))
    comment = None
    if new_regression_notification:
      comment = _TEMPLATE_ISSUE_COMMENT.render(self._GetTemplateArgs(added))
    components, cc, labels = self._ComputeBugUpdate(subscriptions, added)
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        comment,
        summary=summary,
        labels=labels,
        cc_list=cc,
        components=components,
        project=self._group.project_id,
        send_email=False,
    )

  def _FileDuplicatedNotification(self, canonical_group):
    comment = _TEMPLATE_GROUP_WAS_MERGED.render({
        'group': self._group,
        'canonical_group': canonical_group,
    })
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        comment,
        project=self._group.project_id,
        send_email=False,
    )

  def _GetRegressions(self, anomalies):
    regressions = []
    subscriptions_dict = {}
    for a in anomalies:
      # This logging is just for debugging
      # https://bugs.chromium.org/p/chromium/issues/detail?id=1223401
      # in production since I can't reproduce it in unit tests. One theory I
      # have is that there's a bug in this part of the code, where
      # details of one anomaly's subscription get replaced with another
      # anomaly's subscription.
      for s in a.subscriptions:
        if (s.name in subscriptions_dict and s.auto_triage_enable !=
            subscriptions_dict[s.name].auto_triage_enable):
          logging.warn('altered merged auto_triage_enable: %s', s.name)

      subscriptions_dict.update({s.name: s for s in a.subscriptions})
      if not a.is_improvement and not a.recovered:
        regressions.append(a)
    return (regressions, subscriptions_dict.values())

  @classmethod
  def _GetBenchmarksFromRegressions(cls, regressions):
    benchmarks_dict = dict()
    for regression in regressions:
      name = regression.benchmark_name
      emails = []
      info_blurb = None
      if regression.ownership:
        emails = regression.ownership.get('emails') or []
        info_blurb = regression.ownership.get('info_blurb') or ''
      benchmark = benchmarks_dict.get(
          name, cls.BenchmarkDetails(name, list(set(emails)), list(),
                                     info_blurb))
      benchmark.regressions.append(regression)
      benchmarks_dict[name] = benchmark
    return benchmarks_dict.values()

  def _ComputeBugUpdate(self, subscriptions, regressions):
    components = list(
        set(c for s in subscriptions for c in s.bug_components)
        | self._GetComponentsFromRegressions(regressions))
    cc = list(set(e for s in subscriptions for e in s.bug_cc_emails))
    labels = list(
        set(l for s in subscriptions for l in s.bug_labels)
        | {'Chromeperf-Auto-Triaged'})
    # We layer on some default labels if they don't conflict with any of the
    # provided ones.
    if not any(l.startswith('Pri-') for l in labels):
      labels.append('Pri-2')
    if not any(l.startswith('Type-') for l in labels):
      labels.append('Type-Bug-Regression')
    if any(s.visibility == subscription.VISIBILITY.INTERNAL_ONLY
           for s in subscriptions):
      labels = list(set(labels) | {'Restrict-View-Google'})
    return self.BugUpdateDetails(components, cc, labels)

  @staticmethod
  def _GetComponentsFromRegressions(regressions):
    components = []
    for r in regressions:
      component = r.ownership and r.ownership.get('component')
      if not component:
        continue
      if isinstance(component, list) and component:
        components.append(component[0])
      elif component:
        components.append(component)
    return set(components)

  def _GetTemplateArgs(self, regressions):
    # Preparing template arguments used in rendering issue's title and content.
    regressions.sort(key=lambda x: x.relative_delta, reverse=True)
    benchmarks = self._GetBenchmarksFromRegressions(regressions)
    return {
        # Current AlertGroup used for rendering templates
        'group': self._group,

        # Performance regressions sorted by relative difference
        'regressions': regressions,

        # Benchmarks that occur in regressions, including names, owners, and
        # information blurbs.
        'benchmarks': benchmarks,

        # Parse the real unit (remove things like smallerIsBetter)
        'parse_unit': lambda s: (s or '').rsplit('_', 1)[0],
    }

  def _Archive(self):
    self._group.active = False

  def _TryTriage(self, now, anomalies):
    bug, anomalies = self._FileIssue(anomalies)
    if not bug:
      return

    # Update the issue associated with his group, before we continue.
    self._group.bug = bug
    self._group.updated = now
    self._group.status = self._group.Status.triaged
    self._CommitGroup()

    # Link the bug to auto-triage enabled anomalies.
    for a in anomalies:
      if a.bug_id is None and a.auto_triage_enable:
        a.project_id = bug.project
        a.bug_id = bug.bug_id
    ndb.put_multi(anomalies)

  def _AssignIssue(self, regression):
    commit_info = file_bug.GetCommitInfoForAlert(regression, self._crrev,
                                                 self._gitiles)
    if not commit_info:
      return False
    assert self._group.bug is not None

    file_bug.AssignBugToCLAuthor(
        self._group.bug.bug_id,
        commit_info,
        self._issue_tracker,
        labels=['Chromeperf-Auto-Assigned'],
        project=self._group.project_id)
    return True

  def _TryBisect(self, update):
    if (update.issue
        and 'Chromeperf-Auto-BisectOptOut' in update.issue.get('labels')):
      return

    try:
      regressions, _ = self._GetRegressions(update.anomalies)
      regression = self._SelectAutoBisectRegression(regressions)

      # Do nothing if none of the regressions should be auto-bisected.
      if regression is None:
        return

      # We'll only bisect a range if the range at least one point.
      if regression.start_revision == regression.end_revision:
        # At this point we've decided that the range of the commits is a single
        # point, so we don't bother bisecting.
        if not self._AssignIssue(regression):
          self._UpdateWithBisectError(
              update.now, 'Cannot find assignee for regression at %s.' %
              (regression.end_revision,))
        else:
          self._group.updated = update.now
          self._group.status = self._group.Status.bisected
          self._CommitGroup()
        return

      job_id = self._StartPinpointBisectJob(regression)
    except InvalidPinpointRequest as error:
      self._UpdateWithBisectError(update.now, error)
      return

    # Update the issue associated with his group, before we continue.
    self._group.bisection_ids.append(job_id)
    self._group.updated = update.now
    self._group.status = self._group.Status.bisected
    self._CommitGroup()
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        _TEMPLATE_AUTO_BISECT_COMMENT.render(
            {'test': utils.TestPath(regression.test)}),
        labels=['Chromeperf-Auto-Bisected'],
        project=self._group.project_id,
        send_email=False,
    )
    regression.pinpoint_bisects.append(job_id)
    regression.put()

  def _FileIssue(self, anomalies):
    regressions, subscriptions = self._GetRegressions(anomalies)
    # Only file a issue if there is at least one regression
    # We can't use subsciptions' auto_triage_enable here because it's
    # merged across anomalies.
    if not any(r.auto_triage_enable for r in regressions):
      return None, []

    auto_triage_regressions = []
    for r in regressions:
      if r.auto_triage_enable:
        auto_triage_regressions.append(r)
    logging.info('auto_triage_enabled due to %s', auto_triage_regressions)

    template_args = self._GetTemplateArgs(regressions)
    top_regression = template_args['regressions'][0]
    template_args['revision_infos'] = self._revision_info.GetRangeRevisionInfo(
        top_regression.test,
        top_regression.start_revision,
        top_regression.end_revision,
    )
    # Rendering issue's title and content
    title = _TEMPLATE_ISSUE_TITLE.render(template_args)
    description = _TEMPLATE_ISSUE_CONTENT.render(template_args)

    # Fetching issue labels, components and cc from subscriptions and owner
    components, cc, labels = self._ComputeBugUpdate(subscriptions, regressions)
    logging.info('Creating a new issue for AlertGroup %s', self._group.key)

    response = self._issue_tracker.NewBug(
        title,
        description,
        labels=labels,
        components=components,
        cc=cc,
        project=self._group.project_id)
    if 'error' in response:
      logging.warning('AlertGroup file bug failed: %s', response['error'])
      return None, []

    # Update the issue associated witht his group, before we continue.
    return alert_group.BugInfo(
        project=self._group.project_id,
        bug_id=response['bug_id'],
    ), anomalies

  def _StartPinpointBisectJob(self, regression):
    try:
      results = self._pinpoint.NewJob(self._NewPinpointRequest(regression))
    except pinpoint_request.InvalidParamsError as error:
      raise InvalidPinpointRequest('Invalid pinpoint request: %s' % (error,))

    if 'jobId' not in results:
      raise InvalidPinpointRequest('Start pinpoint bisection failed: %s' %
                                   (results,))

    return results.get('jobId')

  def _SelectAutoBisectRegression(self, regressions):
    # Select valid regressions for bisection:
    # 1. auto_bisect_enable
    # 2. has a valid bug_id
    # 3. hasn't start a bisection
    # 4. is not a summary metric (has story)
    regressions = [
        r for r in regressions or []
        if (r.auto_bisect_enable and r.bug_id > 0
            and not set(r.pinpoint_bisects) & set(self._group.bisection_ids)
            and r.test.get().unescaped_story_name)
    ]
    if not regressions:
      return None

    max_regression = None
    max_count = 0

    scores = ndb.get_multi(
        ndb.Key(
            'SignalQuality',
            utils.TestPath(r.test),
            'SignalQualityScore',
            '0',
        ) for r in regressions)
    scores_dict = {s.key.parent().string_id(): s.score for s in scores if s}

    def MaxRegression(x, y):
      if x is None or y is None:
        return x or y

      get_score = lambda a: scores_dict.get(
          utils.TestPath(a.test),
          _ALERT_GROUP_DEFAULT_SIGNAL_QUALITY_SCORE)

      if x.relative_delta == float('Inf'):
        if y.relative_delta == float('Inf'):
          return max(x, y, key=lambda a: (get_score(a), a.absolute_delta))
        else:
          return y
      if y.relative_delta == float('Inf'):
        return x
      return max(x, y, key=lambda a: (get_score(a), a.relative_delta))

    bot_name = lambda r: r.bot_name
    for _, rs in itertools.groupby(
        sorted(regressions, key=bot_name), key=bot_name):
      count = 0
      group_max = None
      for r in rs:
        count += 1
        group_max = MaxRegression(group_max, r)
      if count >= max_count:
        max_count = count
        max_regression = MaxRegression(max_regression, group_max)
    return max_regression

  def _NewPinpointRequest(self, alert):
    start_git_hash = pinpoint_request.ResolveToGitHash(
        alert.start_revision, alert.benchmark_name, crrev=self._crrev)
    end_git_hash = pinpoint_request.ResolveToGitHash(
        alert.end_revision, alert.benchmark_name, crrev=self._crrev)

    # Pinpoint also requires you specify which isolate target to run the
    # test, so we derive that from the suite name. Eventually, this would
    # ideally be stored in a SparseDiagnostic but for now we can guess. Also,
    # Pinpoint only currently works well with Telemetry targets, so we only run
    # benchmarks that are not explicitly denylisted.
    target = pinpoint_request.GetIsolateTarget(alert.bot_name,
                                               alert.benchmark_name)
    if not target:
      return None

    job_name = 'Auto-Bisection on %s/%s' % (alert.bot_name,
                                            alert.benchmark_name)

    alert_magnitude = alert.median_after_anomaly - alert.median_before_anomaly

    return pinpoint_service.MakeBisectionRequest(
        test=alert.test.get(),
        commit_range=pinpoint_service.CommitRange(
            start=start_git_hash, end=end_git_hash),
        issue=anomaly.Issue(
            project_id=self._group.bug.project,
            issue_id=self._group.bug.bug_id,
        ),
        comparison_mode='performance',
        target=target,
        comparison_magnitude=alert_magnitude,
        name=job_name,
        priority=10,
        tags={
            'test_path': utils.TestPath(alert.test),
            'alert': alert.key.urlsafe(),
            'auto_bisection': 'true',
        },
    )

  def _UpdateWithBisectError(self, now, error, labels=None):
    self._group.updated = now
    self._group.status = self._group.Status.bisected
    self._CommitGroup()
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        'Auto-Bisection failed with the following message:\n\n'
        '%s\n\nNot retrying' % (error,),
        labels=labels if labels else ['Chromeperf-Auto-NeedsAttention'],
        project=self._group.project_id)


def _IssueTracker():
  """Get a cached IssueTracker instance."""
  # pylint: disable=protected-access
  if not hasattr(_IssueTracker, '_client'):
    _IssueTracker._client = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
  return _IssueTracker._client
