# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import json
import logging
import os
import shutil
import tempfile

from perf_insights import cloud_storage
from perf_insights import map_runner
from perf_insights import function_handle
from perf_insights.mre import file_handle as file_handle_module
from perf_insights.results import json_output_formatter


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
    th = file_handle_module.GCSFileHandle(trace_url, temp_directory)
    trace_handles.append(th)
  return trace_handles


def Main(argv):
  parser = argparse.ArgumentParser(description=_DEFAULT_DESCRIPTION)
  parser.add_argument('map_file_url')
  parser.add_argument('map_function_name')
  parser.add_argument('input_url')
  parser.add_argument('output_url')
  parser.add_argument('--jobs', type=int, default=1)

  args = parser.parse_args(argv[1:])

  map_file = _ReadMapperGCSFile(args.map_file_url)
  if not map_file:
    parser.error('Map does not exist.')

  if not args.map_function_name:
    parser.error('Must provide map function name.')

  temp_directory = tempfile.mkdtemp()
  _, file_name = tempfile.mkstemp()
  ofile = open(file_name, 'w')

  try:
    output_formatter = json_output_formatter.JSONOutputFormatter(ofile)
    map_function_module = function_handle.ModuleToLoad(
        filename=os.path.abspath(map_file))
    map_function_handle = function_handle.FunctionHandle(
        modules_to_load=[map_function_module],
        function_name=args.map_function_name)

    trace_handles = _DownloadTraceHandles(args.input_url, temp_directory)
    runner = map_runner.MapRunner(trace_handles, map_function_handle,
                                  jobs=args.jobs,
                                  output_formatters=[output_formatter])
    results = runner.Run()

    if args.map_function_handle:
      results = runner.RunMapper()
    elif args.reduce_function_handle:
      results = runner.RunReducer(trace_handles)

    output_formatter.Format(results)

    return results
  finally:
    ofile.close()
    os.unlink(map_file)
    shutil.rmtree(temp_directory)
