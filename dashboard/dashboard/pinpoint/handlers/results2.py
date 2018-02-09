# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for displaying a results2 file."""

import cStringIO
import os
import Queue
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
      output_stream = cStringIO.StringIO()

      render_histograms_viewer.RenderHistogramsViewer(
          histogram_dicts, output_stream,
          vulcanized_html=vulcanized_html)
      self.response.out.write(output_stream.getvalue())

    except Results2Error as e:
      self.response.set_status(400)
      self.response.out.write(e.message)
      return


def _GetJobData(job_id):
  job = job_module.JobFromId(job_id)
  if not job:
    raise Results2Error('Error: Job %s missing' % job_id)

  return job.AsDict(options=(job_module.OPTION_STATE,))


def _ReadVulcanizedHistogramsViewer():
  viewer_path = os.path.join(
      os.path.dirname(__file__), '..', '..', '..',
      'vulcanized_histograms_viewer', 'vulcanized_histograms_viewer.html')
  with open(viewer_path, 'r') as f:
    return f.read()


def _FetchHistogramsDataFromJobData(job_data):
  quest_index = None
  for quest_index in xrange(len(job_data['quests'])):
    if job_data['quests'][quest_index] == 'Test':
      break
  else:
    raise Results2Error('No Test quest.')

  isolate_hashes = []

  # If there are differences, only include Changes with differences.
  for change_index in xrange(len(job_data['changes'])):
    if not _IsChangeDifferent(job_data, change_index):
      continue
    isolate_hashes += _GetIsolateHashesForChange(
        job_data, change_index, quest_index)

  # Otherwise, just include all Changes.
  if not isolate_hashes:
    for change_index in xrange(len(job_data['changes'])):
      isolate_hashes += _GetIsolateHashesForChange(
          job_data, change_index, quest_index)

  # Fetch the histograms in separate threads.
  threads = []
  histogram_queue = Queue.Queue()
  for isolate_hash in isolate_hashes:
    thread = threading.Thread(target=_FetchHistogramFromIsolate,
                              args=(isolate_hash, histogram_queue))
    thread.start()
    threads.append(thread)

  for thread in threads:
    thread.join()

  histograms = []
  while not histogram_queue.empty():
    histograms += histogram_queue.get()
  return histograms


def _IsChangeDifferent(job_data, change_index):
  if (change_index > 0 and
      job_data['comparisons'][change_index - 1] == 'different'):
    return True

  if (change_index < len(job_data['changes']) - 1 and
      job_data['comparisons'][change_index] == 'different'):
    return True

  return False


def _GetIsolateHashesForChange(job_data, change_index, quest_index):
  isolate_hashes = []
  attempts = job_data['attempts'][change_index]
  for attempt_info in attempts:
    executions = attempt_info['executions']
    if quest_index >= len(executions):
      continue

    result_arguments = executions[quest_index]['result_arguments']
    if 'isolate_hash' not in result_arguments:
      continue

    isolate_hashes.append(result_arguments['isolate_hash'])

  return isolate_hashes


def _FetchHistogramFromIsolate(isolate_hash, output_queue):
  output_queue.put(read_value._RetrieveOutputJson(
      isolate_hash, 'chartjson-output.json'))
