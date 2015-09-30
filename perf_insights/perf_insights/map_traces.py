# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import traceback

import perf_insights
from perf_insights import local_directory_corpus_driver
from perf_insights import corpus_query
from perf_insights import map_runner
from perf_insights import map_function_handle as map_function_handle_module
from perf_insights.results import json_output_formatter


def Main(argv):
  parser = argparse.ArgumentParser(
      description='Bulk trace processing')
  parser.add_argument('trace_directory')
  parser.add_argument('--query')
  parser.add_argument('map_file')

  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(argv[1:])

  if not os.path.exists(args.trace_directory):
    parser.error('trace_directory does not exist')
  if not os.path.exists(args.map_file):
    parser.error('map does not exist')

  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(args.trace_directory)))
  if args.query is None:
    query = corpus_query.CorpusQuery.FromString('True')
  else:
    query = corpus_query.CorpusQuery.FromString(
        args.query)

  if args.output_file:
    ofile = open(args.output_file, 'w')
  else:
    ofile = sys.stdout

  output_formatter = json_output_formatter.JSONOutputFormatter(ofile)

  map_function_handle = map_function_handle_module.MapFunctionHandle(
      filename=os.path.abspath(args.map_file))
  try:
    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
    runner = map_runner.MapRunner(trace_handles, map_function_handle,
                    stop_on_error=args.stop_on_error)
    results = runner.Run(jobs=args.jobs, output_formatters=[output_formatter])
    if not results.had_failures:
      return 0
    else:
      return 255
  finally:
    if ofile != sys.stdout:
      ofile.close()
