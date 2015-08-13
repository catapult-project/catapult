# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import codecs
import os
import sys
import traceback
import json

from perf_insights import get_trace_handles_query
from perf_insights import local_directory_corpus_driver
from perf_insights import map_runner
from perf_insights.results import json_output_formatter
from tvcm import generate
import perf_insights
import perf_insights_project


def Main(argv):
  parser = argparse.ArgumentParser(
      description='Local weather report generator')
  parser.add_argument('trace_directory')

  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('-o', '--output-file')
  parser.add_argument('--json', action='store_true')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(argv[1:])
  if not args.output_file:
    parser.error('Must provide -o')

  if not os.path.exists(args.trace_directory):
    parser.error('trace_directory does not exist')


  project = perf_insights_project.PerfInsightsProject()

  results = MapTracesWithWeatherReport(project, args.trace_directory,
                                       stop_on_error=args.stop_on_error,
                                       jobs=args.jobs)
  if args.stop_on_error and results.had_failures:
    sys.stderr.write('There were mapping errors. Aborting.');
    return 255

  if args.json:
    with open(args.output_file, 'w') as ofile:
      json.dump(results.AsDict(), ofile, indent=2)
  else:
    with codecs.open(args.output_file, mode='w', encoding='utf-8') as ofile:
      WriteResultsToFile(ofile, project, results)
  return 0


def MapTracesWithWeatherReport(project, trace_directory,
                               stop_on_error=False,
                               jobs=1):
  map_file = os.path.join(project.perf_insights_src_path,
                          'wr', 'weather_report_map_function.html')

  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(trace_directory)))
  query = get_trace_handles_query.GetTraceHandlesQuery.FromString('True')

  trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
  runner = map_runner.MapRunner(trace_handles, map_file,
                  stop_on_error=stop_on_error)
  return runner.Run(jobs=jobs)


def WriteResultsToFile(ofile, project, results):
  modules = [
      'perf_insights.wr.wr_cmdline'
  ]

  vulcanizer = project.CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(modules)

  results_string = json.dumps(results.AsDict())

  scripts = [DataScript(results_string)]
  generate.GenerateStandaloneHTMLToFile(
      ofile, load_sequence, 'Weather Report', extra_scripts=scripts)


class DataScript(generate.ExtraScript):
  def __init__(self, trace_data_string):
    super(DataScript, self).__init__()
    self._trace_data_string = trace_data_string

  def WriteToFile(self, output_file):
    output_file.write('<script id="wr-data" type="application/json">\n')
    output_file.write(self._trace_data_string)
    output_file.write('\n</script>\n')