# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import codecs
import os
import sys
import json

from perf_insights.mre import corpus_driver_cmdline
from perf_insights.mre import corpus_query
from perf_insights.mre import function_handle
from perf_insights.mre import map_runner
from perf_insights.mre import progress_reporter as progress_reporter_module
from perf_insights.mre import job as job_module
from py_vulcanize import generate
import perf_insights_project
import bs4


def Main(argv, pi_report_file=None):
  parser = argparse.ArgumentParser(
      description='Runs a PerfInsights report and outputs it to html')
  corpus_driver_cmdline.AddArguments(parser)
  if pi_report_file is None:
    parser.add_argument('pi_report_file')

  parser.add_argument('--query')
  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('--json', action='store_true')
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')

  args = parser.parse_args(argv[1:])
  corpus_driver = corpus_driver_cmdline.GetCorpusDriver(parser, args)

  if not args.output_file:
    parser.error('Must provide -o')

  if pi_report_file is None:
    pi_report_file = os.path.abspath(args.pi_report_file)

  if args.query is None:
    query = corpus_query.CorpusQuery.FromString('True')
  else:
    query = corpus_query.CorpusQuery.FromString(
        args.query)

  with codecs.open(args.output_file, mode='w', encoding='utf-8') as ofile:
    return PiReportToHTML(ofile, corpus_driver, pi_report_file, query,
                          args.json, args.stop_on_error, args.jobs)


def _GetMapFunctionHrefFromPiReport(html_contents):
  soup = bs4.BeautifulSoup(html_contents)
  elements = soup.findAll('polymer-element')
  for element in elements:
    if element.attrs.get('extends').lower() == 'pi-ui-r-pi-report':
      map_function_href = element.attrs.get('map-function-href', None)
      if map_function_href is None:
        raise Exception('Report is missing map-function-href attribute')
      map_function_name = element.attrs.get('map-function-name', None)
      if map_function_name is None:
        raise Exception('Report is missing map-function-name attribute')
      pi_report_element_name = element.attrs.get('name', None)
      if pi_report_element_name is None:
        raise Exception('Report is missing name attribute')
      return map_function_href, map_function_name, pi_report_element_name
  raise Exception('No element that extends pi-ui-r-pi-report was found')


def PiReportToHTML(ofile, corpus_driver, pi_report_file, query,
                   json_output=False, stop_on_error=False, jobs=1, quiet=False):
  project = perf_insights_project.PerfInsightsProject()

  with open(pi_report_file, 'r') as f:
    pi_report_file_contents = f.read()

  map_function_href, map_function_name, pi_report_element_name = (
      _GetMapFunctionHrefFromPiReport(pi_report_file_contents))
  map_file = project.GetAbsPathFromHRef(map_function_href)
  module = function_handle.ModuleToLoad(filename=map_file)
  map_function_handle = function_handle.FunctionHandle([module],
                                                       map_function_name)
  job = job_module.Job(map_function_handle, None)

  if map_file == None:
    raise Exception('Could not find %s' % map_function_href)

  results = _MapTraces(corpus_driver, job, query, stop_on_error,
                       jobs, quiet)
  if stop_on_error and results.had_failures:
    sys.stderr.write('There were mapping errors. Aborting.')
    return 255

  if json_output:
    json.dump([result.AsDict() for result in results], ofile, indent=2)
  else:
    WriteResultsToFile(ofile, project,
                       pi_report_file, pi_report_element_name,
                       results)
  return 0


def _MapTraces(corpus_driver, job, query, stop_on_error=False,
               jobs=1, quiet=False):
  trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
  if quiet:
    alt_progress_reporter = progress_reporter_module.ProgressReporter()
  else:
    alt_progress_reporter = None
  runner = map_runner.MapRunner(trace_handles, job,
                  stop_on_error=stop_on_error,
                  progress_reporter=alt_progress_reporter,
                  jobs=jobs)
  return runner.Run()


def WriteResultsToFile(ofile, project,
                       pi_report_file, pi_report_element_name,
                       results):

  vulcanizer = project.CreateVulcanizer()
  modules = []
  modules.append(vulcanizer.LoadModule(
    module_filename=os.path.join(project.perf_insights_root_path,
                                 'perf_insights_build/pi_report_to_html.html')))
  modules.append(vulcanizer.LoadModule(
    module_filename=pi_report_file))

  load_sequence = vulcanizer.CalcLoadSequenceForModules(modules)

  results_string = json.dumps([result.AsDict() for result in results])

  bootstrap_script = generate.ExtraScript(text_content="""
    document.addEventListener('DOMContentLoaded', function() {
      pib.initPiReportNamed('%s');
    });""" % pi_report_element_name)
  scripts = [bootstrap_script, DataScript(results_string)]
  generate.GenerateStandaloneHTMLToFile(
      ofile, load_sequence, 'Perf Insights Report', extra_scripts=scripts)



class DataScript(generate.ExtraScript):
  def __init__(self, trace_data_string):
    super(DataScript, self).__init__()
    self._trace_data_string = trace_data_string

  def WriteToFile(self, output_file):
    output_file.write('<script id="pi-report-data" type="application/json">\n')
    output_file.write(self._trace_data_string)
    output_file.write('\n</script>\n')
