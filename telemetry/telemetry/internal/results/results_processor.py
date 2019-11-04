# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

from tracing.trace_data import trace_data

HTML_TRACE_NAME = 'trace.html'


def SerializeHtmlTraces(results):
  """Creates html trace files for each story run, if necessary.

  For each story run, takes all trace files from individual trace agents
  and runs trace2html on them. This is done only once, subsequent calls to this
  function will not do anything.

  TODO(crbug.com/981349): Remove this function entirely when trace
  serialization has been handed over to results processor.
  """
  assert not results.current_story_run, 'Cannot serialize traces while running.'
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
  try:
    for _ in pool.imap_unordered(_SerializeHtmlTraceInPool, available_runs):
      pass
  finally:
    pool.terminate()
    pool.join()


def _SerializeHtmlTraceInPool(run):
  try:
    html_trace = run.GetArtifact(HTML_TRACE_NAME)
    if html_trace is None:
      trace_files = [art.local_path for art in run.IterArtifacts('trace')]
      with run.CaptureArtifact(HTML_TRACE_NAME) as html_path:
        trace_data.SerializeAsHtml(trace_files, html_path)
  except Exception:  # pylint: disable=broad-except
    # logging exception here is the only way to get a stack trace since
    # multiprocessing's pool implementation does not save that data. See
    # crbug.com/953365.
    logging.exception('%s: Exception while aggregating traces', run.story.name)
    raise
