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
    'Chromeperf Alerts: '
    '{{ regressions|length }} regressions in {{ group.name }}')
_TEMPLATE_ISSUE_CONTENT = _TEMPLATE_ENV.get_template(
    'alert_groups_bug_description.j2')
_TEMPLATE_ISSUE_COMMENT = _TEMPLATE_ENV.get_template(
    'alert_groups_bug_comment.j2')
_TEMPLATE_REOPEN_COMMENT = _TEMPLATE_ENV.get_template('reopen_issue_comment.j2')
_TEMPLATE_AUTO_BISECT_COMMENT = _TEMPLATE_ENV.get_template(
    'auto_bisect_comment.j2')

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
      collections.namedtuple('GroupUpdate', ('now', 'anomalies', 'issue'))):
    __slots__ = ()

  class BenchmarkDetails(
      collections.namedtuple('BenchmarkDetails',
                             ('name', 'bot', 'owners', 'regressions'))):
    __slots__ = ()

  class BugUpdateDetails(
      collections.namedtuple('BugUpdateDetails',
                             ('components', 'cc', 'labels'))):
    __slots__ = ()

  def __init__(self,
               group,
               config=None,
               sheriff_config=None,
               issue_tracker=None,
               pinpoint=None,
               crrev=None,
               gitiles=None):
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

  def _PrepareGroupUpdate(self):
    now = datetime.datetime.utcnow()
    query = anomaly.Anomaly.query(anomaly.Anomaly.groups.IN([self._group.key]))
    anomalies = query.fetch()
    issue = None
    if self._group.status in {
        self._group.Status.triaged, self._group.Status.bisected,
        self._group.Status.closed
    }:
      issue = self._issue_tracker.GetIssue(
          self._group.bug.bug_id, project=self._group.bug.project)
    return self.GroupUpdate(now, anomalies, issue)

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

    update = update or self._PrepareGroupUpdate()

    # Process input before we start processing the group.
    for a in update.anomalies:
      subscriptions, _ = self._sheriff_config.Match(
          a.test.string_id(), check=True)
      a.subscriptions = subscriptions
      a.auto_triage_enable = any(s.auto_triage_enable for s in subscriptions)
      a.auto_bisect_enable = any(s.auto_bisect_enable for s in subscriptions)
      a.relative_delta = (
          abs(a.absolute_delta / float(a.median_before_anomaly))
          if a.median_before_anomaly != 0. else float('Inf'))

    added = self._UpdateAnomalies(update.anomalies)
    if update.issue:
      self._UpdateStatus(update.issue)
      self._UpdateIssue(update.issue, update.anomalies, added)
    # Trigger actions
    group = self._group
    if group.updated + self._config.active_window < update.now and (
        group.status in {group.Status.untriaged, group.Status.closed}):
      self._Archive()
    elif group.created + self._config.triage_delay < update.now and (
        group.status in {group.Status.untriaged}):
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

  def _UpdateIssue(self, issue, anomalies, added):
    for a in anomalies:
      if a.bug_id is None and a.auto_triage_enable:
        a.project_id = self._group.project_id
        a.bug_id = self._group.bug.bug_id

    # Write back bug_id to anomalies. We can't do it when anomaly is
    # found because group may be updating at the same time.
    ndb.put_multi(anomalies)

    # Check whether all the anomalies associated have been marked recovered.
    if all(a.recovered for a in anomalies if not a.is_improvement):
      return self._CloseBecauseRecovered()

    regressions, subscriptions = self._GetRegressions(added)

    # Only update issue if there is at least one regression
    if not regressions or not any(r.auto_triage_enable for r in regressions):
      return

    if issue.get('state') == 'closed':
      self._ReopenWithNewRegressions(regressions, subscriptions)
    else:
      self._FileNormalUpdate(regressions, subscriptions)

  def _CloseBecauseRecovered(self):
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        'All regressions for this issue have been marked recovered; closing.',
        status='WontFix',
        labels='Chromeperf-Auto-Closed',
        project=self._group.project_id)

  def _ReopenWithNewRegressions(self, regressions, subscriptions):
    template_args = self._GetTemplateArgs(regressions)
    comment = _TEMPLATE_REOPEN_COMMENT.render(template_args)
    components, cc, _ = self._ComputeBugUpdate(subscriptions, regressions)
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        comment,
        components=components,
        labels=['Chromeperf-Auto-Reopened'],
        status='Unconfirmed',
        cc_list=cc,
        project=self._group.project_id)

  def _FileNormalUpdate(self, regressions, subscriptions):
    template_args = self._GetTemplateArgs(regressions)
    comment = _TEMPLATE_ISSUE_COMMENT.render(template_args)
    components, cc, labels = self._ComputeBugUpdate(subscriptions, regressions)
    self._issue_tracker.AddBugComment(
        self._group.bug.bug_id,
        comment,
        labels=labels,
        cc_list=cc,
        components=components,
        project=self._group.project_id)

  def _GetRegressions(self, anomalies):
    regressions = []
    subscriptions_dict = {}
    for a in anomalies:
      subscriptions_dict.update({s.name: s for s in a.subscriptions})
      if not a.is_improvement and not a.recovered:
        regressions.append(a)
    return (regressions, subscriptions_dict.values())

  @classmethod
  def _GetBenchmarksFromRegressions(cls, regressions):
    benchmarks_dict = dict()
    for regression in regressions:
      name = regression.benchmark_name
      benchmark = benchmarks_dict.get(
          name, cls.BenchmarkDetails(name, regression.bot_name, set(), []))
      if regression.ownership:
        emails = regression.ownership.get('emails') or []
        benchmark.owners.update(emails)
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
        | set(['Chromeperf-Auto-Triaged']))
    # We layer on some default labels if they don't conflict with any of the
    # provided ones.
    if not any(l.startswith('Pri-') for l in labels):
      labels.append('Pri-2')
    if not any(l.startswith('Type-') for l in labels):
      labels.append('Type-Bug-Regression')
    if any(s.visibility == subscription.VISIBILITY.INTERNAL_ONLY
           for s in subscriptions):
      labels = list(set(labels) | set(['Restrict-View-Google']))
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

        # Benchmarks that occur in regressions, including names and owners
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
        project=self._group.project_id)
    regression.pinpoint_bisects.append(job_id)
    regression.put()

  def _FileIssue(self, anomalies):
    regressions, subscriptions = self._GetRegressions(anomalies)
    # Only file a issue if there is at least one regression
    # We can't use subsciptions' auto_triage_enable here because it's
    # merged across anomalies.
    if not any(r.auto_triage_enable for r in regressions):
      return None, []

    template_args = self._GetTemplateArgs(regressions)
    # Rendering issue's title and content
    title = _TEMPLATE_ISSUE_TITLE.render(template_args)
    description = _TEMPLATE_ISSUE_CONTENT.render(template_args)

    # Fetching issue labels, components and cc from subscriptions and owner
    components, cc, labels = self._ComputeBugUpdate(subscriptions, regressions)

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
    regressions = [
        r for r in regressions or []
        if (r.auto_bisect_enable and r.bug_id > 0
            and not set(r.pinpoint_bisects) & set(self._group.bisection_ids))
    ]
    if not regressions:
      return None

    max_regression = None
    max_count = 0

    def MaxRegression(x, y):
      if x is None or y is None:
        return x or y
      if x.relative_delta == float('Inf'):
        if y.relative_delta == float('Inf'):
          return max(x, y, key=lambda a: a.absolute_delta)
        else:
          return y
      if y.relative_delta == float('Inf'):
        return x
      return max(x, y, key=lambda a: a.relative_delta)

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
    # benchmarks that are not explicitly blacklisted.
    target = pinpoint_request.GetIsolateTarget(
        alert.bot_name,
        alert.benchmark_name,
        alert.start_revision,
        alert.end_revision,
        only_telemetry=True)
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
