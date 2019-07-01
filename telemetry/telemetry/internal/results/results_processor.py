# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import random
import sys
import time
import uuid

import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.value import common_value_helpers
from tracing.metrics import metric_runner
from tracing.trace_data import trace_data

HTML_TRACE_NAME = 'trace.html'

_TEN_MINUTES = 60*10


#TODO(crbug.com/772216): Remove this once the uploading is done by Chromium
# test recipe.
def UploadArtifactsToCloud(results):
  """Upload all artifacts of the test to cloud storage.

  Sets 'url' attribute of each artifact to its cloud URL.
  """
  bucket = results.telemetry_info.upload_bucket
  for run in results.all_page_runs:
    for artifact in run.IterArtifacts():
      if artifact.url is None:
        remote_name = str(uuid.uuid1())
        cloud_url = cloud_storage.Insert(
            bucket, remote_name, artifact.local_path)
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
  label = results.telemetry_info.label,
  bucket = results.telemetry_info.upload_bucket
  for run in results.IterRunsWithTraces():
    _SerializeAndUploadHtmlTrace(run, label, bucket)


def ComputeTimelineBasedMetrics(results):
  """Compute TBMv2 metrics on all story runs in parallel."""
  assert not results.current_page_run, 'Cannot compute metrics while running.'
  def _GetCpuCount():
    try:
      return multiprocessing.cpu_count()
    except NotImplementedError:
      # Some platforms can raise a NotImplementedError from cpu_count()
      logging.warn('cpu_count() not implemented.')
      return 8

  runs_with_traces = list(results.IterRunsWithTraces())
  if not runs_with_traces:
    return

  # Note that this is speculatively halved as an attempt to fix
  # crbug.com/953365.
  threads_count = min(_GetCpuCount()/2 or 1, len(runs_with_traces))
  pool = ThreadPool(threads_count)
  metrics_runner = lambda run: _ComputeMetricsInPool(
      run,
      results.telemetry_info.label,
      results.telemetry_info.upload_bucket)

  try:
    for result in pool.imap_unordered(metrics_runner, runs_with_traces):
      results.AddMetricPageResults(result)
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
  story_name = run.story.name
  try:
    retvalue = {
        'run': run,
        'fail': [],
        'histogram_dicts': None,
        'scalars': []
    }
    extra_import_options = {
        'trackDetailedModelStats': True
    }

    html_trace = _SerializeAndUploadHtmlTrace(run, label, bucket)
    trace_size_in_mib = os.path.getsize(html_trace.local_path) / (2 ** 20)
    # Bails out on trace that are too big. See crbug.com/812631 for more
    # details.
    if trace_size_in_mib > 400:
      retvalue['fail'].append(
          '%s: Trace size is too big: %s MiB' % (story_name, trace_size_in_mib))
      return retvalue

    logging.info('%s: Starting to compute metrics on trace.', story_name)
    start = time.time()
    # This timeout needs to be coordinated with the Swarming IO timeout for the
    # task that runs this code. If this timeout is longer or close in length
    # to the swarming IO timeout then we risk being forcibly killed for not
    # producing any output. Note that this could be fixed by periodically
    # outputing logs while waiting for metrics to be calculated.
    timeout = _TEN_MINUTES
    mre_result = metric_runner.RunMetricOnSingleTrace(
        html_trace.local_path, run.tbm_metrics,
        extra_import_options, canonical_url=html_trace.url,
        timeout=timeout)
    logging.info('%s: Computing metrics took %.3f seconds.' % (
        story_name, time.time() - start))

    if mre_result.failures:
      for f in mre_result.failures:
        retvalue['fail'].append('%s: %s' % (story_name, str(f)))

    histogram_dicts = mre_result.pairs.get('histograms', [])
    retvalue['histogram_dicts'] = histogram_dicts

    scalars = []
    for d in mre_result.pairs.get('scalars', []):
      scalars.append(common_value_helpers.TranslateScalarValue(
          d, run.story))
    retvalue['scalars'] = scalars
    return retvalue
  except Exception:  # pylint: disable=broad-except
    # logging exception here is the only way to get a stack trace since
    # multiprocessing's pool implementation does not save that data. See
    # crbug.com/953365.
    logging.exception('%s: Exception while calculating metric', story_name)
    raise
