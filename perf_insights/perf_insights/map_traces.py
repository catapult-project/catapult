# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import traceback

import perf_insights
from perf_insights import local_directory_corpus_driver
from perf_insights import perf_insights_corpus_driver
from perf_insights import corpus_query
from perf_insights import map_runner
from perf_insights import map_function_handle as map_function_handle_module
from perf_insights.results import json_output_formatter


# TODO(simonhatch): Use telemetry's discover.py module once its part of
# catapult.
_CORPUS_DRIVERS = {
  'perf-insights': {
      'description': 'Use the performance insights server.',
      'class': perf_insights_corpus_driver.PerfInsightsCorpusDriver
  },
  'local-directory': {
      'description': 'Use traces from a local directory.',
      'class': local_directory_corpus_driver.LocalDirectoryCorpusDriver
  },
  'list': None
}
_CORPUS_DRIVER_DEFAULT = 'perf-insights'


def Main(argv):
  parser = argparse.ArgumentParser(
      description='Bulk trace processing')
  parser.add_argument(
      '-c', '--corpus',
      choices=_CORPUS_DRIVERS.keys(),
      default=_CORPUS_DRIVER_DEFAULT)
  parser.add_argument('--query')
  parser.add_argument('map_file')

  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')

  for k, v in _CORPUS_DRIVERS.iteritems():
    if not v:
      continue
    parser_group = parser.add_argument_group(k)
    driver_cls = v['class']
    driver_cls.AddArguments(parser_group)

  args = parser.parse_args(argv[1:])

  # With parse_known_args, optional arguments aren't guaranteed to be there so
  # we need to check if it's there, and use the default otherwise.
  corpus = _CORPUS_DRIVER_DEFAULT
  if hasattr(args, 'corpus'):
    corpus = args.corpus

  if corpus == 'list':
    corpus_descriptions = '\n'.join(
        ['%s: %s' % (k, v['description'])
            for k, v in _CORPUS_DRIVERS.iteritems() if v]
      )
    parser.exit('Valid drivers:\n\n%s\n' % corpus_descriptions)

  cls = _CORPUS_DRIVERS[corpus]['class']
  cls.CheckArguments(parser, args)
  corpus_driver = cls(args)

  if not os.path.exists(args.map_file):
    parser.error('map does not exist')

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
