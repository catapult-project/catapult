# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cloudstorage
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard.pinpoint.models.quest import read_value
from tracing_build import render_histograms_viewer


class Results2Error(Exception):

  pass


class CachedResults2(ndb.Model):
  """Stores data on when a results2 was generated."""

  updated = ndb.DateTimeProperty(required=True, auto_now_add=True)
  job_id = ndb.StringProperty()


class _GcsFileStream(object):
  """Wraps a gcs file providing a FileStream like api."""

  # pylint: disable=invalid-name

  def __init__(self, *args, **kwargs):
    self._gcs_file = cloudstorage.open(*args, **kwargs)

  def seek(self, _):
    pass

  def truncate(self):
    pass

  def write(self, data):
    self._gcs_file.write(data)

  def close(self):
    self._gcs_file.close()


def _GetCloudStorageName(job_id):
  return '/results2-public/%s.html' % job_id


def GetCachedResults2(job):
  filename = _GetCloudStorageName(job.job_id)
  results = cloudstorage.listbucket(filename)

  for _ in results:
    return 'https://storage.cloud.google.com' + filename

  return None


def ScheduleResults2Generation(job):
  try:
    # Don't want several tasks creating results2, so create task with specific
    # name to deduplicate.
    task_name = 'results2-public-%s' % job.job_id
    taskqueue.add(
        queue_name='job-queue', url='/api/generate-results2/' + job.job_id,
        name=task_name)
  except taskqueue.TombstonedTaskError:
    return False
  except taskqueue.TaskAlreadyExistsError:
    pass
  return True


def GenerateResults2(job):
  histogram_dicts = _FetchHistograms(job)
  vulcanized_html = _ReadVulcanizedHistogramsViewer()

  CachedResults2(job_id=job.job_id).put()

  filename = _GetCloudStorageName(job.job_id)
  gcs_file = _GcsFileStream(
      filename, 'w', content_type='text/html',
      retry_params=cloudstorage.RetryParams(backoff_factor=1.1))

  render_histograms_viewer.RenderHistogramsViewer(
      histogram_dicts, gcs_file,
      reset_results=True, vulcanized_html=vulcanized_html)

  gcs_file.close()


def _ReadVulcanizedHistogramsViewer():
  viewer_path = os.path.join(
      os.path.dirname(__file__), '..', '..', '..',
      'vulcanized_histograms_viewer', 'vulcanized_histograms_viewer.html')
  with open(viewer_path, 'r') as f:
    return f.read()


def _FetchHistograms(job):
  for change in _ChangeList(job):
    for attempt in job.state._attempts[change]:
      for execution in attempt.executions:
        if not isinstance(
            execution, read_value._ReadHistogramsJsonValueExecution):
          continue

        # The histogram sets are very big. Since we have limited
        # memory, delete the histogram sets as we go along.
        histogram_set = _HistogramSetFromExecution(execution)
        for histogram in histogram_set:
          yield histogram
        del histogram_set


def _ChangeList(job):
  # If there are differences, only include Changes with differences.
  changes = []

  for change_a, change_b in job.state.Differences():
    if change_a not in changes:
      changes.append(change_a)
    if change_b not in changes:
      changes.append(change_b)

  if changes:
    return changes

  return job.state._changes


def _HistogramSetFromExecution(execution):
  if hasattr(execution, '_isolate_server'):
    isolate_server = execution._isolate_server
  else:
    isolate_server = 'https://isolateserver.appspot.com'
  isolate_hash = execution._isolate_hash
  if hasattr(execution, '_results_filename'):
    results_filename = execution._results_filename
  else:
    results_filename = 'chartjson-output.json'
  return read_value._RetrieveOutputJson(
      isolate_server, isolate_hash, results_filename)
