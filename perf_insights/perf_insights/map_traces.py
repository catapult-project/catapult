# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import traceback

import perf_insights
from perf_insights import corpus_driver_cmdline
from perf_insights import corpus_query
from perf_insights import map_runner
from perf_insights import function_handle
from perf_insights.results import json_output_formatter


_CORPUS_QUERY_HELP = """
Overview of corpus query syntax:

<query> := <condition> [AND <condition> ...] [ MAX_TRACE_HANDLES=<int>]
<condition> := <property> {< | <= | > | >= | = | != } <value>
<condition> := <property> IN <list>
<property> := {date | network_type | prod | remote_addr | tags |
               user_agent | ver}
<list> := (<value> [, <value> ...])
<value> := numeric, string, or Date(YYYY-MM-DD HH:MM:SS.SS)

Examples:
  --query "date >= Date(2015-10-15 00:00:00.00) AND prod = 'test'"
  --query "remote_addr = '128.0.0.1' AND MAX_TRACE_HANDLES=10"
"""


def Main(argv):
  parser = argparse.ArgumentParser(
      description='Bulk trace processing')
  corpus_driver_cmdline.AddArguments(parser)
  parser.add_argument('--query')
  parser.add_argument('map_file')
  parser.add_argument('-j', '--jobs', type=int,
                      default=map_runner.AUTO_JOB_COUNT)
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')

  args = parser.parse_args(argv[1:])
  corpus_driver = corpus_driver_cmdline.GetCorpusDriver(parser, args)

  if not os.path.exists(args.map_file):
    parser.error('Map does not exist.')

  if args.query == 'help':
    parser.exit(_CORPUS_QUERY_HELP)
  elif args.query is None:
    query = corpus_query.CorpusQuery.FromString('True')
  else:
    query = corpus_query.CorpusQuery.FromString(args.query)

  if args.output_file:
    ofile = open(args.output_file, 'w')
  else:
    ofile = sys.stdout

  output_formatter = json_output_formatter.JSONOutputFormatter(ofile)

  map_function_handle = function_handle.FunctionHandle(
      filename=os.path.abspath(args.map_file))
  try:
    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
    runner = map_runner.MapRunner(trace_handles, map_function_handle,
                                  stop_on_error=args.stop_on_error,
                                  jobs=args.jobs,
                                  output_formatters=[output_formatter])
    results = runner.Run()
    if not results.had_failures:
      return 0
    else:
      return 255
  finally:
    if ofile != sys.stdout:
      ofile.close()
