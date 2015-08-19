# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoints to show and gather stats on performance and alerts.

StatsHandler is the main entry point, and provides the interface for requesting
statistics to be generated and viewing generated statistics.

This module also contains other handlers for gathering statistics Test by Test,
since querying all Tests at once puts us over the 60s timeout.
"""

import collections
import datetime
import json
import math

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import math_utils
from dashboard import request_handler
from dashboard import utils
from dashboard import xsrf
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import sheriff

# Buckets to split alerts into based on relative change size.
_PERCENT_CHANGED_BUCKETS = [1, 2, 5, 10, 20]

# Task queue name, should be present in queue.yaml.
_QUEUE_NAME = 'stats-queue'


class StatContainer(ndb.Model):
  """Represents a set of statistics that is displayed together."""
  # Type of statistics, e.g. 'around_revision' or 'alerts_summary'.
  stat_type = ndb.StringProperty()
  # A dictionary of information about the set of statistics overall.
  summary = ndb.JsonProperty()
  # Number of individual items in this set of statistics.
  num_stats = ndb.IntegerProperty()
  # Time that this entity was created.
  timestamp = ndb.DateTimeProperty(auto_now_add=True, indexed=True)


class IndividualStat(ndb.Model):
  """Represents one item within a set of statistics."""
  # A dictionary which could contain different things for different types of
  # statistics; could contain information about one Test or one day.
  details = ndb.JsonProperty()


class StatsHandler(request_handler.RequestHandler):
  """URL endpoint to request/view stats."""

  def get(self):
    """Shows a set of statistics, or a form for producing stats."""
    if not utils.IsInternalUser():
      self.RenderHtml('result.html', {
          'errors': ['Only logged-in internal users can access stats.']
      })
      return

    key = self.request.get('key')
    if key:
      self._DisplayResults(key)
    else:
      self._DisplayForm()

  def _DisplayResults(self, key):
    """Displays a set of previously-generated statistics."""
    container = ndb.Key(urlsafe=key).get()
    stats = IndividualStat.query(ancestor=container.key).fetch()
    total = container.num_stats
    processed = len(stats)
    title = self._GetStatTitle(container)

    if processed < total:
      have_stats = False
      stat_type = None
      processed_stats = None
    else:
      have_stats = True
      stat_type = container.stat_type
      if stat_type == 'around_revision':
        processed_stats = self._GetAroundRevisionStats(container, stats)
      elif stat_type == 'alert_summary':
        processed_stats = self._GetAlertSummaryStats(container, stats)

    self.RenderHtml('stats.html', {
        'title': title,
        'waiting': not have_stats,
        'have_stats': have_stats,
        'type': stat_type,
        'stats': processed_stats,
        'processed': processed,
        'total': total,
    })

  def _DisplayForm(self):
    """Displays a form for requesting a set of statistics."""
    master = ndb.Key('Master', 'ChromiumPerf')
    bots = graph_data.Bot.query(ancestor=master).fetch(keys_only=True)
    bots = [b.string_id() for b in bots]
    sheriffs = sheriff.Sheriff.query().fetch(keys_only=True)
    sheriffs = [s.string_id() for s in sheriffs]
    recent_stats = StatContainer.query().order(
        -StatContainer.timestamp).fetch(limit=20)
    recent = []
    for r in recent_stats:
      recent.append({
          'key': r.key.urlsafe(),
          'title': self._GetStatTitle(r),
      })

    self.RenderHtml('stats.html', {
        'recent': recent,
        'bots': bots,
        'sheriffs': sheriffs,
    })

  def _GetStatTitle(self, container):
    """Returns a title string for the given stat container."""
    title_prefix = ''
    if container.summary.get('name'):
      title_prefix = '%s: ' % container.summary.get('name')

    if container.stat_type == 'around_revision':
      revision = container.summary.get('revision')
      num_around = container.summary.get('num_around')
      return ('%sChanges around revision %s (%s points each direction)' %
              (title_prefix, revision, num_around))

    if container.stat_type == 'alert_summary':
      start = container.summary.get('start_date')
      end = container.summary.get('end_date')
      return '%s: %s-%s' % (title_prefix, start, end)

  def _GetAroundRevisionStats(self, container, stats):
    """Fetches the template variables needed to display around-revision stats.

    Args:
      container: A StatContainer entity.
      stats: A list of IndividualStat entities.

    Returns:
      A dictionary.
    """
    data = {
        'revision': int(container.summary['revision']),
        'num_around': int(container.summary['num_around']),
        'tests': [],
    }
    for stat in stats:
      data['tests'].append(stat.details)
    return data

  def _GetAlertSummaryStats(self, container, stats):
    """Gets all the template variables needed to display alert summary stats.

    Args:
      container: A StatContainer entity.
      stats: A list of IndividualStat entities.

    Returns:
      A dictionary.
    """
    def IndividualStatTimeInt(individual_stat):
      date = individual_stat.details['date']
      return (int(date.split('-')[0]) * 10000 +
              int(date.split('-')[1]) * 100 +
              int(date.split('-')[2]))

    stats.sort(key=IndividualStatTimeInt)
    details = [s.details for s in stats]
    categories = [
        'bots',
        'test_suites',
        'traces',
        'bug_ids',
        'percent_changed_buckets',
    ]
    axis_map = {i: d['date'] for i, d in enumerate(details)}
    overall_summaries = {}
    daily_summaries = {}
    for category in categories:
      key_names = set()
      for d in details:
        key_names |= set(d.get(category, {}))
      overall_summaries[category] = []
      daily_summaries[category] = []
      for key_name in key_names:
        pie_dict = {
            'label': key_name,
            'data': sum(d.get(category, {}).get(key_name, 0) for d in details)
        }
        overall_summaries[category].append(pie_dict)
        daily_dict = {'label': key_name, 'data': []}
        for i, d in enumerate(details):
          yval = d.get(category, {}).get(key_name, 0)
          daily_dict['data'].append([i, yval])
        daily_summaries[category].append(daily_dict)
      # Sort by percent.
      if category != 'percent_changed_buckets':
        overall_summaries[category].sort(key=lambda d: d['data'])

    data = {
        'start_date': container.summary['start_date'],
        'end_date': container.summary['end_date'],
        'alert_summaries': [s.details for s in stats],
        'axis_map': json.dumps(axis_map),
        'overall_summaries': json.dumps(overall_summaries),
        'daily_summaries': json.dumps(daily_summaries),
    }
    return data

  @xsrf.TokenRequired
  def post(self):
    """Kicks off a task on the task queue to generate the requested stats."""
    if not utils.IsInternalUser():
      self.RenderHtml('result.html', {
          'errors': ['Only logged-in internal users can access stats.']
      })
      return

    datastore_hooks.SetPrivilegedRequest()
    stat_type = self.request.get('type')
    stat_container = StatContainer(stat_type=stat_type)

    if stat_type == 'around_revision':
      self._StartGeneratingStatsAroundRevision(stat_container)
    elif stat_type == 'alert_summary':
      self._StartGeneratingStatsForAlerts(stat_container)
    self.redirect('/stats?key=%s' % stat_container.key.urlsafe())

  def _StartGeneratingStatsAroundRevision(self, stat_container):
    """Adds tasks for generating around_revision stats to the task queue.

    Note: Master and sheriff are hard-coded below. If we want to use this
    to generate stats about other masters or sheriffs, we should:
      1. Make master and sheriff specified by parameters.
      2. Add fields on the form to specify these parameters.

    Args:
      stat_container: A StatContainer entity to populate.
    """
    bots = self.request.get_all('bots')
    bots = ['ChromiumPerf/' + bot for bot in bots]
    sheriff_key = ndb.Key('Sheriff', 'Chromium Perf Sheriff')
    test_query = graph_data.Test.query(graph_data.Test.sheriff == sheriff_key)
    test_keys = test_query.fetch(keys_only=True)
    test_keys = [k for k in test_keys if '/'.join(
        utils.TestPath(k).split('/')[:2]) in bots]
    summary = {
        'revision': int(self.request.get('rev')),
        'num_around': int(self.request.get('num_around')),
        'name': self.request.get('name', None),
    }
    stat_container.summary = summary
    stat_container.num_stats = len(test_keys)
    stat_container.put()
    for test_key in test_keys:
      taskqueue.add(url='/stats_around_revision',
                    params={
                        'revision': summary['revision'],
                        'num_around': summary['num_around'],
                        'test_key': test_key.urlsafe(),
                        'parent_key': stat_container.key.urlsafe(),
                    },
                    queue_name=_QUEUE_NAME)

  def _StartGeneratingStatsForAlerts(self, stat_container):
    """Adds tasks for generating alert_summary stats to the task queue.

    Args:
      stat_container: A StatContainer entity to populate.
    """
    def DateParts(date_string):
      """Returns the year, month, day numbers in a yyyy-mm-dd string."""
      return map(int, date_string.split('-'))
    start_date = datetime.datetime(*DateParts(self.request.get('start_date')))
    end_date = datetime.datetime(*DateParts(self.request.get('end_date')))

    sheriff_name = self.request.get('sheriff')
    stat_container.summary = {
        'name': self.request.get('name', None),
        'start_date': self.request.get('start_date'),
        'end_date': self.request.get('end_date'),
        'sheriff': sheriff_name,
    }
    stat_container.num_stats = 0
    stat_container.put()

    date_to_enqueue = start_date
    while date_to_enqueue <= end_date:
      taskqueue.add(url='/stats_for_alerts',
                    params={
                        'sheriff': sheriff_name,
                        'year': date_to_enqueue.year,
                        'month': date_to_enqueue.month,
                        'day': date_to_enqueue.day,
                        'parent_key': stat_container.key.urlsafe(),
                    },
                    queue_name=_QUEUE_NAME)
      date_to_enqueue += datetime.timedelta(days=1)
      stat_container.num_stats += 1
    stat_container.put()


class StatsAroundRevisionHandler(request_handler.RequestHandler):
  """URL endpoint for tasks which generate stats before/after a revision."""

  def post(self):
    """Task queue task to get stats before/after a revision of a single Test.

    Request parameters:
      revision: A central revision to look around.
      num_around: The number of points before and after the given revision.
      test_key: The urlsafe string of a Test key.
      parent_key: The urlsafe string of a StatContainer key.
    """
    datastore_hooks.SetPrivilegedRequest()

    revision = int(self.request.get('revision'))
    num_around = int(self.request.get('num_around'), 10)
    test_key = ndb.Key(urlsafe=self.request.get('test_key'))
    container_key = ndb.Key(urlsafe=self.request.get('parent_key'))

    # Get the Rows and values before and starting from the given revision.
    before_revs = graph_data.Row.query(
        graph_data.Row.parent_test == test_key,
        graph_data.Row.revision < revision).order(
            -graph_data.Row.revision).fetch(limit=num_around)
    before_vals = [b.value for b in before_revs]
    after_revs = graph_data.Row.query(
        graph_data.Row.parent_test == test_key,
        graph_data.Row.revision >= revision).order(
            graph_data.Row.revision).fetch(limit=num_around)
    after_vals = [a.value for a in after_revs]

    # There may be no Row at the particular revision requested; if so, we use
    # the first revision after the given revision.
    actual_revision = None
    if after_vals:
      actual_revision = after_revs[0].revision

    test = test_key.get()
    improvement_direction = self._ImprovementDirection(test)
    median_before = math_utils.Median(before_vals)
    median_after = math_utils.Median(after_vals)
    mean_before = math_utils.Median(before_vals)
    mean_after = math_utils.Median(after_vals)
    details = {
        'test_path': utils.TestPath(test_key),
        'improvement_direction': improvement_direction,
        'actual_revision': actual_revision,
        'median_before': '%.2f' % median_before,
        'median_after': '%.2f' % median_after,
        'median_percent_improved': self._PercentImproved(
            median_before, median_after, improvement_direction),
        'mean_before': '%.2f' % mean_before,
        'mean_after': '%.2f' % mean_after,
        'mean_percent_improved': self._PercentImproved(
            mean_before, mean_after, improvement_direction),
        'std': '%.2f' % math_utils.StandardDeviation(before_vals + after_vals),
    }
    new_stat = IndividualStat(parent=container_key, details=details)
    new_stat.put()

  def _ImprovementDirection(self, test):
    """Returns a string describing improvement direction of a Test."""
    if test.improvement_direction == anomaly.UP:
      return 'up'
    if test.improvement_direction == anomaly.DOWN:
      return 'down'
    return 'unknown'

  def _PercentImproved(self, before, after, improvement_direction):
    """Returns a string containing percent improvement."""
    if math.isnan(before) or math.isnan(after):
      return 'NaN'
    if before == 0:
      return anomaly.FREAKIN_HUGE
    percent_improved = ((after - before) / before) * 100
    if improvement_direction == 'down' and percent_improved != 0:
      percent_improved = -percent_improved
    return '%.2f' % percent_improved


class StatsForAlertsHandler(request_handler.RequestHandler):
  """URL endpoint for tasks which generate stats about alerts."""

  def post(self):
    """Task queue task to process a single day's alerts for a sheriff."""
    datastore_hooks.SetPrivilegedRequest()
    container_key = ndb.Key(urlsafe=self.request.get('parent_key'))
    sheriff_key = ndb.Key('Sheriff', self.request.get('sheriff'))
    year = int(self.request.get('year'))
    month = int(self.request.get('month'))
    day = int(self.request.get('day'))

    # Fetch all of the alerts for the day.
    start_time = datetime.datetime(year, month, day)
    end_time = start_time + datetime.timedelta(days=1)
    alerts = anomaly.Anomaly.query(
        anomaly.Anomaly.timestamp >= start_time,
        anomaly.Anomaly.timestamp < end_time,
        anomaly.Anomaly.sheriff == sheriff_key).fetch()

    details = collections.defaultdict(dict)
    details['date'] = '%s-%s-%s' % (year, month, day)
    for alert in alerts:
      self._AddAlert(alert, details)
    new_stat = IndividualStat(parent=container_key, details=details)
    new_stat.put()

  def _IncrementDict(self, dictionary, key):
    """Increments a count in a dictionary."""
    dictionary[key] = dictionary.get(key, 0) + 1

  def _AddAlert(self, anomaly_entity, details):
    """Adds the given Anomaly to the stats for the day.

    Args:
      anomaly_entity: An Anomaly entity.
      details: A dictionary of details for one IndividualStat.
    """
    test_path_parts = anomaly_entity.test.flat()[1::2]
    bot = '%s/%s' % (test_path_parts[0], test_path_parts[1])
    suite = test_path_parts[2]
    test = '/'.join(test_path_parts[2:])
    trace = anomaly_entity.test.string_id()
    percent_changed_bucket = self._PercentChangedBucket(
        anomaly_entity.percent_changed)

    # Increment counts for each category that this alert belongs to.
    self._IncrementDict(details['bots'], bot)
    self._IncrementDict(details['test_suites'], suite)
    self._IncrementDict(details['tests'], test)
    self._IncrementDict(details['traces'], trace)
    if anomaly_entity.bug_id:
      self._IncrementDict(details['bug_ids'], anomaly_entity.bug_id)
    self._IncrementDict(details['percent_changed_buckets'],
                        percent_changed_bucket)

  def _PercentChangedBucket(self, percent_changed):
    """Returns the name of a percent-changed bucket to put alerts into."""
    percent_changed = abs(percent_changed)
    percent_changed_bucket = None
    for bucket in _PERCENT_CHANGED_BUCKETS:
      if percent_changed < bucket:
        return '%02d%%' % bucket
    if not percent_changed_bucket:
      return 'largest'
