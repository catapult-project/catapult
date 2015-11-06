# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import Queue as queue
import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import traceback

import perf_insights
from perf_insights import cloud_storage
from perf_insights import gcs_trace_handle
from perf_insights import map_runner
from perf_insights import function_handle
from perf_insights.results import json_output_formatter
from perf_insights.value import run_info as run_info_module


_DEFAULT_PARALLEL_DOWNLOADS = 16
_DEFAULT_DESCRIPTION = """
Entry point for the cloud mapper. Please consider using
perf_insights/bin/map_traces for normal development."""


def _ReadMapperGCSFile(url):
  file_handle, file_name = tempfile.mkstemp()
  try:
    cloud_storage.Copy(url, file_name)
  except cloud_storage.CloudStorageError as e:
    logging.info("Failed to copy: %s" % e)
    os.close(file_handle)
    os.unlink(file_name)
    file_name = None
  return file_name


def _ReadTracesGCSFile(url):
  file_handle, file_name = tempfile.mkstemp()
  file_urls = []
  try:
    cloud_storage.Copy(url, file_name)
    with open(file_name, 'r') as f:
      file_urls = json.loads(f.read())
  except cloud_storage.CloudStorageError as e:
    logging.info("Failed to copy: %s" % e)
  finally:
    os.close(file_handle)
    os.unlink(file_name)
  return file_urls


def _DownloadTraceHandles(url, temp_directory):
  trace_urls = _ReadTracesGCSFile(url)

  trace_handles = []
  for trace_url in trace_urls:
    run_info = run_info_module.RunInfo(
        url=trace_url,
        display_name=trace_url,
        run_id=trace_url)

    th = gcs_trace_handle.GCSTraceHandle(run_info, temp_directory)
    trace_handles.append(th)
  return trace_handles


def Main(argv):
  parser = argparse.ArgumentParser(description=_DEFAULT_DESCRIPTION)
  parser.add_argument('map_file_url')
  parser.add_argument('input_url')
  parser.add_argument('output_url')
  parser.add_argument('--jobs', type=int, default=1)

  args = parser.parse_args(argv[1:])

  map_file = _ReadMapperGCSFile(args.map_file_url)
  if not map_file:
    parser.error('Map does not exist.')

  temp_directory = tempfile.mkdtemp()
  _, file_name = tempfile.mkstemp()
  ofile = open(file_name, 'w')

  try:
    output_formatter = json_output_formatter.JSONOutputFormatter(ofile)
    map_function_handle = function_handle.FunctionHandle(
        filename=os.path.abspath(map_file))

    trace_handles = _DownloadTraceHandles(args.input_url, temp_directory)
    runner = map_runner.MapRunner(trace_handles, map_function_handle,
                                  jobs=args.jobs,
                                  output_formatters=[output_formatter])
    results = runner.Run()

    # TODO: gsutil cp file_name gs://output
    cloud_storage.Copy(file_name, args.output_url)

    if not results.had_failures:
      return 0
    else:
      return 255
  finally:
    ofile.close()
    os.unlink(map_file)
    shutil.rmtree(temp_directory)
