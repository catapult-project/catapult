# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import sys
import uuid

import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

from py_utils import cloud_storage  # pylint: disable=import-error

from tracing.trace_data import trace_data

HTML_TRACE_NAME = 'trace.html'


#TODO(crbug.com/772216): Remove this once the uploading is done by Chromium
# test recipe.
def UploadArtifactsToCloud(results):
  """Upload all artifacts of the test to cloud storage.

  Sets 'url' attribute of each artifact to its cloud URL.
  """
  for run in results.IterStoryRuns():
    for artifact in run.IterArtifacts():
      if artifact.url is None:
        remote_name = str(uuid.uuid1())
        cloud_url = cloud_storage.Insert(
            results.upload_bucket, remote_name, artifact.local_path)
        logging.info('Uploading %s of page %s to %s\n' % (
            artifact.name, run.story.name, cloud_url))
        artifact.SetUrl(cloud_url)


def SerializeAndUploadHtmlTraces(results):
  """Creates and uploads html trace files for each story run, if necessary.

  For each story run, takes all trace files from individual trace agents
  and runs trace2html on them. Then uploads the resulting html to cloud.
  This is done only once, subsequent calls to this function will not
  do anything.
  """
  for run in results.IterRunsWithTraces():
    _SerializeAndUploadHtmlTrace(run, results.label, results.upload_bucket)


def ComputeTimelineBasedMetrics(results):
  """DEPRECATED: (Used to) compute TBMv2 metrics on all story runs in parallel.

  Note: This function no longer does any metric computation, but it is still
  used to serialize and upload traces in parallel.

  TODO(crbug.com/981349): Remove this function entirely when trace
  serialization and upload have been handed over to results processor.
  """
  assert not results.current_story_run, 'Cannot compute metrics while running.'
  def _GetCpuCount():
    try:
      return multiprocessing.cpu_count()
    except NotImplementedError:
      # Some platforms can raise a NotImplementedError from cpu_count()
      logging.warn('cpu_count() not implemented.')
      return 8

  available_runs = list(run for run in results.IterRunsWithTraces())
  if not available_runs:
    return

  # Note that this is speculatively halved as an attempt to fix
  # crbug.com/953365.
  threads_count = min(_GetCpuCount()/2 or 1, len(available_runs))
  pool = ThreadPool(threads_count)
  metrics_runner = lambda run: _ComputeMetricsInPool(
      run, results.label, results.upload_bucket)

  try:
    for _ in pool.imap_unordered(metrics_runner, available_runs):
      pass
  finally:
    pool.terminate()
    pool.join()


def _TraceCanonicalName(run, label):
  parts = [
      run.story.file_safe_name,
      label,
      run.start_datetime.strftime('%Y-%m-%d_%H-%M-%S'),
      random.randint(1, 1e5)]
  return '_'.join(str(p) for p in parts if p) + '.html'


def _SerializeAndUploadHtmlTrace(run, label, bucket):
  html_trace = run.GetArtifact(HTML_TRACE_NAME)
  if html_trace is None:
    trace_files = [art.local_path for art in run.IterArtifacts('trace')]
    with run.CaptureArtifact(HTML_TRACE_NAME) as html_path:
      trace_data.SerializeAsHtml(trace_files, html_path)

  html_trace = run.GetArtifact(HTML_TRACE_NAME)
  if bucket is not None and html_trace.url is None:
    remote_name = _TraceCanonicalName(run, label)
    cloud_url = cloud_storage.Insert(bucket, remote_name, html_trace.local_path)
    sys.stderr.write(
        'View generated trace files online at %s for story %s\n' % (
            cloud_url, run.story.name))
    html_trace.SetUrl(cloud_url)

  return html_trace


def _ComputeMetricsInPool(run, label, bucket):
  # TODO(crbug.com/981349): Remove when superceeded by results processor.
  try:
    _SerializeAndUploadHtmlTrace(run, label, bucket)
  except Exception:  # pylint: disable=broad-except
    # logging exception here is the only way to get a stack trace since
    # multiprocessing's pool implementation does not save that data. See
    # crbug.com/953365.
    logging.exception('%s: Exception while aggregating traces', run.story.name)
    raise
