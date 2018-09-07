# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import httplib
import time

from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard import add_histograms
from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import job_state

from tracing.value import histogram as histogram_module
from tracing.value import histogram_set
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos

_MAX_JOBS_TO_FETCH = 100


class UpdateDashboardStatsHandler(request_handler.RequestHandler):
  """A simple request handler to refresh the cached test suites info."""

  def get(self):
    datastore_hooks.SetPrivilegedRequest()
    _FetchDashboardStats()


def _FetchCompletedPinpointJobs(start_date):
  query = job_module.Job.query().order(-job_module.Job.created)
  jobs, next_cursor, more = query.fetch_page(_MAX_JOBS_TO_FETCH)

  def _IsValidJob(job):
    if job.status != 'Completed':
      return False
    if not job.bug_id:
      return False
    if not hasattr(job.state, '_comparison_mode'):
      return False
    if job.state.comparison_mode != job_state.PERFORMANCE:
      return False
    diffs = len(list(job.state.Differences()))
    if diffs != 1:
      return False
    return True

  jobs_in_range = [j for j in jobs if j.created > start_date]
  valid_jobs = [j for j in jobs_in_range if _IsValidJob(j)]
  total_jobs = []
  total_jobs.extend(valid_jobs)

  while jobs_in_range and more:
    jobs, next_cursor, more = query.fetch_page(
        _MAX_JOBS_TO_FETCH, start_cursor=next_cursor)
    jobs_in_range = [j for j in jobs if j.created > start_date]
    valid_jobs = [j for j in jobs_in_range if _IsValidJob(j)]
    total_jobs.extend(valid_jobs)

  total_jobs = [(j, _GetDiffCommitTimeFromJob(j)) for j in total_jobs]
  total_jobs = [(j, c) for j, c in total_jobs if c]

  return total_jobs


def _CreateHistogramSet(
    master, bot, benchmark, commit_position, histograms):
  histograms = histogram_set.HistogramSet(histograms)
  histograms.AddSharedDiagnostic(
      reserved_infos.MASTERS.name,
      generic_set.GenericSet([master]))
  histograms.AddSharedDiagnostic(
      reserved_infos.BOTS.name,
      generic_set.GenericSet([bot]))
  histograms.AddSharedDiagnostic(
      reserved_infos.CHROMIUM_COMMIT_POSITIONS.name,
      generic_set.GenericSet([commit_position]))
  histograms.AddSharedDiagnostic(
      reserved_infos.BENCHMARKS.name,
      generic_set.GenericSet([benchmark]))

  return histograms


def _CreateHistogram(name, story=None):
  h = histogram_module.Histogram(name, 'msBestFitFormat')
  if story:
    h.diagnostics[reserved_infos.STORIES.name] = (
        generic_set.GenericSet([story]))
  return h


def _GetDiffCommitTimeFromJob(job):
  diffs = job.state.Differences()
  try:
    for d in diffs:
      diff = d[1].AsDict()
      commit_time = datetime.datetime.strptime(
          diff['commits'][0]['time'], '%a %b %d %X %Y')
      return commit_time
  except httplib.HTTPException:
    return None


@ndb.tasklet
def _FetchStatsForJob(job, commit_time):
  culprit_time = job.updated
  create_time = job.created

  # Alert time, we'll approximate this out by querying for all alerts for this
  # bug and taking the earliest.
  query = anomaly.Anomaly.query()
  query = query.filter(anomaly.Anomaly.bug_id == job.bug_id)
  alerts = yield query.fetch_async(limit=1000)
  if not alerts:
    raise ndb.Return(None)

  alert_time = min([a.timestamp for a in alerts])
  if alert_time < commit_time:
    raise ndb.Return(None)

  time_from_job_to_culprit = (
      culprit_time - create_time).total_seconds() * 1000.0
  time_from_commit_to_alert = (
      alert_time - commit_time).total_seconds() * 1000.0
  time_from_alert_to_job = (
      create_time - alert_time).total_seconds() * 1000.0
  time_from_commit_to_culprit = (
      culprit_time - commit_time).total_seconds() * 1000.0

  raise ndb.Return((
      time_from_commit_to_culprit,
      time_from_commit_to_alert,
      time_from_alert_to_job,
      time_from_job_to_culprit))


@ndb.synctasklet
def _FetchDashboardStats():
  process_alerts_future = _ProcessAlerts()

  completed_jobs = _FetchCompletedPinpointJobs(
      datetime.datetime.now() - datetime.timedelta(days=14))

  yield [
      _ProcessPinpointJobs(completed_jobs),
      process_alerts_future]


@ndb.tasklet
def _ProcessAlerts():
  sheriff = ndb.Key('Sheriff', 'Chromium Perf Sheriff')
  ts_start = datetime.datetime.now() - datetime.timedelta(days=1)

  q = anomaly.Anomaly.query()
  q = q.filter(anomaly.Anomaly.timestamp > ts_start)
  q = q.filter(anomaly.Anomaly.sheriff == sheriff)
  q = q.order(-anomaly.Anomaly.timestamp)

  alerts = yield q.fetch_async()
  if not alerts:
    raise ndb.Return()

  alerts_total = _CreateHistogram('chromium.perf.alerts')
  alerts_total.AddSample(len(alerts))

  count_by_suite = {}

  for a in alerts:
    test_suite_name = utils.TestSuiteName(a.test)
    if test_suite_name not in count_by_suite:
      count_by_suite[test_suite_name] = 0
    count_by_suite[test_suite_name] += 1

  hists_by_suite = {}
  for s, c in count_by_suite.iteritems():
    hists_by_suite[s] = _CreateHistogram('chromium.perf.alerts', story=s)
    hists_by_suite[s].AddSample(c)

  hs = _CreateHistogramSet(
      'ChromiumPerfFyi', 'test1', 'chromeperf.stats', int(time.time()),
      [alerts_total] + hists_by_suite.values())

  deferred.defer(
      add_histograms.ProcessHistogramSet, hs.AsDicts())


@ndb.tasklet
def _ProcessPinpointJobs(jobs_and_commits):
  job_results = yield [_FetchStatsForJob(j, c) for j, c in jobs_and_commits]
  job_results = [j for j in job_results if j]
  if not job_results:
    raise ndb.Return(None)

  commit_to_culprit = _CreateHistogram('pinpoint')
  commit_to_alert = _CreateHistogram('pinpoint', story='commitToAlert')
  alert_to_job = _CreateHistogram('pinpoint', story='alertToJob')
  job_to_culprit = _CreateHistogram('pinpoint', story='jobToCulprit')

  for result in job_results:
    time_from_land_to_culprit = result[0]
    time_from_commit_to_alert = result[1]
    time_from_alert_to_job = result[2]
    time_from_job_to_culprit = result[3]

    commit_to_alert.AddSample(time_from_commit_to_alert)
    alert_to_job.AddSample(time_from_alert_to_job)
    job_to_culprit.AddSample(time_from_job_to_culprit)
    commit_to_culprit.AddSample(time_from_land_to_culprit)

  hs = _CreateHistogramSet(
      'ChromiumPerfFyi', 'test1', 'chromeperf.stats', int(time.time()),
      [commit_to_alert, alert_to_job, job_to_culprit, commit_to_culprit])

  deferred.defer(
      add_histograms.ProcessHistogramSet, hs.AsDicts())
