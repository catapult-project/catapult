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
# pylint: disable=too-many-lines

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import datetime
import itertools
import jinja2
import json
import logging
import os
import six

from google.appengine.api import datastore_errors
from google.appengine.ext import ndb

from dashboard import pinpoint_request
from dashboard import sheriff_config_client
from dashboard import revision_info_client
from dashboard.common import cloud_metric
from dashboard.common import file_bug
from dashboard.common import sandwich_allowlist
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import skia_helper
from dashboard.models import subscription
from dashboard.services import crrev_service
from dashboard.services import gitiles_service
from dashboard.services import perf_issue_service_client
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
_TEMPLATE_AUTO_REGRESSION_VERIFICATION_COMMENT = _TEMPLATE_ENV.get_template(
    'auto_regression_verification_comment.j2')
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


class AlertGroupWorkflow:
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
    if issue.get('status') != perf_issue_service_client.STATUS_DUPLICATE:
      return None

    merged_into = issue.get('mergedInto', {}).get('issueId', None)
    if not merged_into:
      return None
    logging.info('Found canonical issue for the groups\' issue: %d',
                 merged_into)

    merged_issue_project = issue.get('mergedInto',
                                     {}).get('projectId',
                                             self._group.bug.project)
    query = alert_group.AlertGroup.query(
        alert_group.AlertGroup.active == True,
        alert_group.AlertGroup.bug.project == merged_issue_project,
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

    # Parity check for canonical group
    try:
      canonical_group_new = perf_issue_service_client.GetCanonicalGroupByIssue(
          self._group.key.string_id(), merged_into, merged_issue_project)
      canonical_group_key = canonical_group_new.get('key')
      original_canonical_key = canonical_group.key.string_id()
      if original_canonical_key != canonical_group_key:
        logging.warning('Imparity found for GetCanonicalGroupByIssue. %s, %s',
                        original_canonical_key, canonical_group_key)
        cloud_metric.PublishPerfIssueServiceGroupingImpariry(
            'GetCanonicalGroupByIssue')
      logging.info('Found canonical group: %s', canonical_group_key)
      canonical_group = ndb.Key('AlertGroup', canonical_group_key).get()

      return canonical_group
    except Exception as e:  # pylint: disable=broad-except
      logging.warning('Parity logic failed in GetCanonicalGroupByIssue. %s',
                      str(e))


  def _FindDuplicateGroupKeys(self):
    try:
      group_keys = perf_issue_service_client.GetDuplicateGroupKeys(
          self._group.key.string_id())
      return group_keys
    except (ValueError, datastore_errors.BadValueError):
      # only 'ungrouped' has integer key, which we should not find duplicate.
      return []

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

    # Parity check for duplicated groups
    try:
      duplicate_group_keys = self._FindDuplicateGroupKeys()
      original_keys = [g.key.string_id() for g in duplicate_groups]
      if sorted(duplicate_group_keys) != sorted(original_keys):
        logging.warning('Imparity found for _FindDuplicateGroups. %s, %s',
                        duplicate_group_keys, original_keys)
        cloud_metric.PublishPerfIssueServiceGroupingImpariry(
            '_FindDuplicateGroups')
    except Exception as e:  # pylint: disable=broad-except
      logging.warning('Parity logic failed in _FindDuplicateGroups. %s', str(e))

    duplicate_groups = [
        ndb.Key('AlertGroup', k).get() for k in duplicate_group_keys
    ]
    anomalies = self._FindRelatedAnomalies([self._group] + duplicate_groups)

    now = datetime.datetime.utcnow()
    issue = None
    canonical_group = None
    if self._group.status in {
        self._group.Status.triaged, self._group.Status.bisected,
        self._group.Status.closed
    }:
      project_name = self._group.bug.project or 'chromium'
      issue = perf_issue_service_client.GetIssue(
          self._group.bug.bug_id, project_name=project_name)
      if issue:
        issue['comments'] = perf_issue_service_client.GetIssueComments(
            self._group.bug.bug_id, project_name=project_name)
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
      logging.error('No anomalies detected. Skipping this run.')
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

    # anomaly.groups are updated in upload-processing. Here we update
    # the group.anomalies
    added = self._UpdateAnomalies(update.anomalies)

    if update.issue:
      group_merged = self._UpdateCanonicalGroup(update.anomalies,
                                                update.canonical_group)
      # Update the group status.
      self._UpdateStatus(update.issue)
      # Update the anomalies to associate with an issue.
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
    # TODO(crbug/1454620): Add logic to start sandwich verification when
    # the regression has not yet been verified and to start bisection if
    # the bug is verified or there are no regressions in sandwich allowlist
    # TODO(crbug/1454620): replace with group.Status.verified_regressions
    # and update
    # third_party/catapult/dashboard/dashboard/models/alert_group.py;l=48
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

    # Only update issue if there is at least one new regression
    if not new_regressions:
      return False

    closed_by_pinpoint = False
    for c in sorted(
        issue.get('comments') or [], key=lambda c: c["id"], reverse=True):
      if c.get('updates', {}).get('status') in ('WontFix', 'Fixed', 'Verified',
                                                'Invalid', 'Duplicate', 'Done'):
        closed_by_pinpoint = (
            c.get('author') in [
                self._service_account(), utils.LEGACY_SERVICE_ACCOUNT
            ])
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
      return

    self._FileNormalUpdate(
        all_regressions,
        new_regressions,
        subscriptions,
        new_regression_notification=False)

  def _CloseBecauseRecovered(self):
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment='All regressions for this issue have been marked recovered; closing.',
        status='WontFix',
        labels='Chromeperf-Auto-Closed',
        send_email=False,
    )

  def _ReopenWithNewRegressions(self, all_regressions, added, subscriptions):
    summary = _TEMPLATE_ISSUE_TITLE.render(
        self._GetTemplateArgs(all_regressions))
    comment = _TEMPLATE_REOPEN_COMMENT.render(self._GetTemplateArgs(added))
    components, cc, _ = self._ComputeBugUpdate(subscriptions, added)
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment=comment,
        title=summary,
        components=components,
        labels=['Chromeperf-Auto-Reopened'],
        status='Unconfirmed',
        cc=cc,
        send_email=False,
    )

  def _UpdateRegressionVerification(self, execution, regression):
    '''Update regression verification results in monorail.

    This is a placeholder function and will likely need to be refactored
    once the rest of the sandwich verification workflow lands.

    Args:
      execution - the response from workflow_client.GetExecution()
      regression - the candidate regression that was sent for verification
    '''

    status = 'Unconfirmed'
    if execution.state == 'ACTIVE':
      return
    if execution.state == 'SUCCEEDED':
      results_dict = json.loads(execution.result)
      if 'decision' in results_dict:
        decision = results_dict['decision']
      else:
        raise ValueError('execution %s result is missing parameters: %s' %
                         (execution.name, results_dict))
      logging.info(
          'Regression verification %s for project: %s and '
          'bug: %s succeeded with repro decision %s.', execution.name,
          self._group.project_id, self._group.bug.bug_id, decision)
      if decision:
        comment = ('Regression verification %s job %s for test: %s\n'
                   'reproduced the regression with statistic: %s\n.'
                   'Proceed to bisection.' %
                   (execution.name, results_dict['job_id'], regression.test,
                    results_dict['statistic']))
        label = 'Regression-Verification-Repro'
        status = 'Available'
      else:
        comment = ('Regression verification %s job %s for test: %s\n'
                   'did NOT reproduce the regression with statistic: %s.'
                   'Issue closed.' %
                   (execution.name, results_dict['job_id'], regression.test,
                    results_dict['statistic']))
        label = ['Regression-Verification-No-Repro', 'Chromeperf-Auto-Closed']
        status = 'WontFix'
      # TODO(sunxiaodi): add components to the monorail post.
    elif execution.state == 'FAILED':
      logging.error(
          'Regression verification %s for project: %s and '
          'bug: %s failed with error %s.', execution.name,
          self._group.project_id, self._group.bug.bug_id, execution.error)
      comment = ('Regression verification %s for test: %s\n'
                 'failed. Proceed to bisection.' %
                 (execution.name, regression.test))
      label = 'Regression-Verification-Failed'
    elif execution.state == 'CANCELLED':
      logging.info(
          'Regression verification %s for project: %s and '
          'bug: %s cancelled with error %s.', execution.name,
          self._group.project_id, self._group.bug.bug_id, execution.error)
      comment = ('Regression verification %s for test: %s\n'
                 'cancelled with message %s. Proceed to bisection.' %
                 (execution.name, regression.test, execution.error))
      label = 'Regression-Verification-Cancelled'
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment=comment,
        labels=label,
        status=status,
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
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment=comment,
        title=summary,
        labels=labels,
        cc=cc,
        components=components,
        send_email=False,
    )

  def _FileDuplicatedNotification(self, canonical_group):
    comment = _TEMPLATE_GROUP_WAS_MERGED.render({
        'group': self._group,
        'canonical_group': canonical_group,
    })
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment=comment,
        send_email=False,
    )

  def _GetRegressions(self, anomalies):
    regressions = []
    subscriptions_dict = {}
    for a in anomalies:
      logging.info(
          'GetRegressions: auto_triage_enable is %s for anomaly %s due to subscription: %s',
          a.auto_triage_enable,
          a.test.string_id(),
          [s.name for s in a.subscriptions])

      subscriptions_dict.update({s.name: s for s in a.subscriptions})
      if not a.is_improvement and not a.recovered and a.auto_triage_enable:
        regressions.append(a)
    return (regressions, list(subscriptions_dict.values()))

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
    return list(benchmarks_dict.values())

  def _ComputeBugUpdate(self, subscriptions, regressions):
    components = list(
        self._GetComponentsFromSubscriptions(subscriptions)
        | self._GetComponentsFromRegressions(regressions))
    if len(components) != 1:
      logging.warning('Invalid component count is found for bug update: %s',
                      components)
      cloud_metric.PublistPerfIssueInvalidComponentCount(len(components))
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

  def _GetComponentsFromSubscriptions(self, subscriptions):
    components = set(c for s in subscriptions for c in s.bug_components)
    if components:
      bug_id = self._group.bug or 'New'
      subsciption_names = [s.name for s in subscriptions]
      logging.debug(
          'Components added from subscriptions. Bug: %s, subscriptions: %s, components: %s',
          bug_id, subsciption_names, components)
    return components

  def _GetComponentsFromRegressions(self, regressions):
    components = []
    for r in regressions:
      component = r.ownership and r.ownership.get('component')
      if not component:
        continue
      if isinstance(component, list) and component:
        components.append(component[0])
      elif component:
        components.append(component)
    if components:
      bug_id = self._group.bug or 'New'
      benchmarks = [r.benchmark_name for r in regressions]
      logging.debug(
          'Components added from benchmark.Info. Bug: %s, benchmarks: %s, components: %s',
          bug_id, benchmarks, components)
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
        labels=['Chromeperf-Auto-Assigned'],
        project=self._group.project_id)
    return True

  def _CheckSandwichAllowlist(self, regressions): # pylint: disable=unused-argument
    """Filter list of regressions against the sandwich verification
    allowlist and improvement direction.

    Args:
      regressions: A list of regressions in the anomaly group.

    Returns:
      allowed_regressions: A list of sandwich verifiable regressions.
    """
    allowed_regressions = []

    for regression in regressions:
      benchmark = regression.benchmark_name
      bot = regression.bot_name
      if bot in sandwich_allowlist.ALLOWABLE_DEVICES and \
        benchmark in sandwich_allowlist.ALLOWABLE_BENCHMARKS and \
        regression.is_improvement:
        allowed_regressions.append(regression)

    return allowed_regressions

  def _TryVerifyRegression(self, update):
    """Verify the selected regression using the sandwich verification workflow.

    Args:
      update: An alert group containing anomalies and potential regressions

    Returns:
      True or False.
    """
    # Do not run sandwiching if anomaly subscription opts out of culprit finding
    if (update.issue
        and 'Chromeperf-Auto-BisectOptOut' in update.issue.get('labels')):
      return False

    # check if any regressions qualify for verification
    regressions, _ = self._GetRegressions(update.anomalies)
    verifiable_regressions = self._CheckSandwichAllowlist(regressions)
    regression = self._SelectAutoBisectRegression(verifiable_regressions)

    if not regression:
      return False

    self._StartPinpointTryJob(regression)

    # TODO(crbug/1454620): Update the issue associated with this group,
    # using the same logic in _TryBisect. Use
    # _TEMPLATE_AUTO_REGRESSION_VERIFICATION_COMMENT as the bug template

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
    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment=_TEMPLATE_AUTO_BISECT_COMMENT.render(
            {'test': utils.TestPath(regression.test)}),
        labels=['Chromeperf-Auto-Bisected'],
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

    try:
      skia_url = skia_helper.GetSkiaUrlForRegressionGroup(
          regressions, self._crrev, self._gitiles)
      logging.info('Skia Perf Url: %s', skia_url)
      template_args['skia_url'] = skia_url
    except Exception as e:  # pylint: disable=broad-except
      logging.error('Error generating skia perf links: %s', str(e))

    # Rendering issue's title and content
    title = _TEMPLATE_ISSUE_TITLE.render(template_args)
    description = _TEMPLATE_ISSUE_CONTENT.render(template_args)

    # Fetching issue labels, components and cc from subscriptions and owner
    components, cc, labels = self._ComputeBugUpdate(subscriptions, regressions)
    logging.info('Creating a new issue for AlertGroup %s', self._group.key)

    response = perf_issue_service_client.PostIssue(
        title=title,
        description=description,
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
        bug_id=response['issue_id'],
    ), anomalies

  def _StartPinpointTryJob(self, regression): # pylint: disable=unused-argument
    """Call sandwich verification workflow to kick off a verification try job

    Args:
      regression: A regression in a CABE compatible benchmark/workload/device

    Returns:
      job_id: A string representing the Pinpoint job ID
    """
    raise NotImplementedError("crbug/1454620")

  def _StartPinpointBisectJob(self, regression):
    try:
      results = self._pinpoint.NewJob(self._NewPinpointRequest(regression))
    except pinpoint_request.InvalidParamsError as e:
      six.raise_from(
          InvalidPinpointRequest('Invalid pinpoint request: %s' % (e,)), e)

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
        alert.start_revision - 1, alert.benchmark_name, crrev=self._crrev)
    end_git_hash = pinpoint_request.ResolveToGitHash(
        alert.end_revision, alert.benchmark_name, crrev=self._crrev)
    logging.info(
        """
        Making new pinpoint request. Alert start revision: %s; end revision: %s.
         Pinpoint start hash (one position back): %s, end hash: %s'
         """, alert.start_revision, alert.end_revision, start_git_hash,
        end_git_hash)

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
            'alert': six.ensure_str(alert.key.urlsafe()),
            'auto_bisection': 'true',
        },
    )

  def _UpdateWithBisectError(self, now, error, labels=None):
    self._group.updated = now
    self._group.status = self._group.Status.bisected
    self._CommitGroup()

    perf_issue_service_client.PostIssueComment(
        self._group.bug.bug_id,
        self._group.project_id,
        comment='Auto-Bisection failed with the following message:\n\n'
        '%s\n\nNot retrying' % (error,),
        labels=labels if labels else ['Chromeperf-Auto-NeedsAttention'],
    )
