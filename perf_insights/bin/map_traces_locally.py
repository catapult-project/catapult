# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import traceback

import perf_insights
from perf_insights import local_directory_corpus_driver
from perf_insights import get_trace_handles_query
from perf_insights import map_single_trace
from perf_insights import json_map_results


def Main(args):
  parser = argparse.ArgumentParser(
      description='Local bulk trace processing')
  parser.add_argument('trace_directory')
  parser.add_argument('corpus_query_string')
  parser.add_argument('map_file')

  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(args)

  if not os.path.exists(args.trace_directory):
    args.error('trace_directory does not exist')
  if not os.path.exists(args.map_file):
    args.error('map does not exist')

  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(args.trace_directory)))
  query = get_trace_handles_query.GetTraceHandlesQuery.FromString(
      args.corpus_query_string)

  if args.output_file:
    ofile = open(args.output_file, 'w')
  else:
    ofile = sys.stdout

  map_results = json_map_results.JSONMapResults(ofile)
  try:
    _Run(map_results, corpus_driver, query, args.map_file,
         stop_on_error=args.stop_on_error)
  finally:
    if ofile != sys.stdout:
      ofile.close()

  if map_results.had_failures:
    return 255
  return 0

def _Run(map_results, corpus_driver, query, map_file,
         stop_on_error=False):

  trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)

  map_results.WillMapTraces()

  failure_to_dump = None
  for trace_handle in trace_handles:
    map_results.WillMapSingleTrace(trace_handle)
    result_value = map_single_trace.MapSingleTrace(
        trace_handle,
        os.path.abspath(map_file))
    map_results.DidMapSingleTrace(trace_handle, result_value)
    if stop_on_error and result['type'] == 'failure':
      failure_to_dump = (trace_handle, result_value)
      break
  map_results.DidMapTraces()

  if failure_to_dump:
    sys.stderr.write('\n\nWhile mapping %s:\n' %
                     failure_to_dump[0].run_info.display_name)
    sys.stderr.write(failure_to_dump[1]['stack_str'])
    sys.stderr.write('\n')