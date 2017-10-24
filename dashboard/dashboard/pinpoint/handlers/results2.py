# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for displaying a results2 file."""

import os
import StringIO
import threading
import webapp2

from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models.quest import read_value
from tracing_build import render_histograms_viewer


class Results2Error(Exception):

  pass


class Results2(webapp2.RequestHandler):
  """Shows an overview of recent anomalies for perf sheriffing."""

  def get(self, job_id):
    try:
      job_data = _GetJobData(job_id)

      histogram_dicts = _FetchHistogramsDataFromJobData(job_data)

      vulcanized_html = _ReadVulcanizedHistogramsViewer()
      vulcanized_html_and_histograms = StringIO.StringIO()
      render_histograms_viewer.RenderHistogramsViewer(
          histogram_dicts, vulcanized_html_and_histograms,
          vulcanized_html=vulcanized_html)
      self.response.out.write(vulcanized_html_and_histograms.getvalue())
    except Results2Error as e:
      self.response.set_status(400)
      self.response.out.write(e.message)
      return


def _ReadVulcanizedHistogramsViewer():
  viewer_path = os.path.join(
      os.path.dirname(__file__), '..', '..', '..',
      'vulcanized_histograms_viewer', 'vulcanized_histograms_viewer.html')
  with open(viewer_path, 'r') as f:
    return f.read()


def _FetchHistogramsDataFromJobData(job_data):
  histogram_dicts = []
  threads = []
  lock = threading.Lock()

  test_index = -1
  for i in xrange(len(job_data['quests'])):
    if job_data['quests'][i] == 'Test':
      test_index = i
      break

  if test_index == -1:
    raise Results2Error('No Test quest.')

  for current_attempt in job_data['attempts']:
    for execution_dict in current_attempt:
      executions = execution_dict.get('executions')
      if not executions:
        continue
      result_arguments = executions[test_index].get('result_arguments', {})
      isolate_hash = result_arguments.get('isolate_hash')
      if not isolate_hash:
        continue

      t = threading.Thread(
          target=_FetchHistogramFromIsolate,
          args=(isolate_hash, histogram_dicts, lock))
      threads.append(t)

  # We use threading since httplib2 provides no async functions.
  for t in threads:
    t.start()
  for t in threads:
    t.join()

  return histogram_dicts


def _GetJobData(job_id):
  job = job_module.JobFromId(job_id)
  if not job:
    raise Results2Error('Error: Job %s missing' % job_id)

  job_data = job.AsDict()
  return job_data


def _FetchHistogramFromIsolate(isolate_hash, histogram_dicts, lock):
  histogram_output = read_value._RetrieveOutputJson(
      isolate_hash, 'chartjson-output.json')
  if not histogram_output:
    return
  with lock:
    histogram_dicts.extend(histogram_output)
