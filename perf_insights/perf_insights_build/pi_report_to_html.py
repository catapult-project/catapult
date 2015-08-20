# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import codecs
import os
import sys
import traceback
import json

from perf_insights import corpus_query
from perf_insights import local_directory_corpus_driver
from perf_insights import map_function_handle as map_function_handle_module
from perf_insights import map_runner
from perf_insights.results import json_output_formatter
from tvcm import generate
import perf_insights
import perf_insights_project
import polymer_soup


def Main(argv, pi_report_file=None):
  parser = argparse.ArgumentParser(
      description='Runs a PerfInsights report and outputs it to html')
  parser.add_argument('trace_directory')
  if pi_report_file is None:
    parser.add_argument('pi_report_file')

  parser.add_argument('--query')
  parser.add_argument('-j', '--jobs', type=int, default=1)
  parser.add_argument('--json', action='store_true')
  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(argv[1:])
  if not args.output_file:
    parser.error('Must provide -o')

  if pi_report_file is None:
    pi_report_file = os.path.abspath(args.pi_report_file)

  if not os.path.exists(args.trace_directory):
    parser.error('trace_directory does not exist')

  if args.query is None:
    query = corpus_query.CorpusQuery.FromString('True')
  else:
    query = corpus_query.CorpusQuery.FromString(
        args.query)

  return PiReportToHTML(args.output_file, args.trace_directory,
                        pi_report_file, query, args.json,
                        args.stop_on_error, args.jobs)

def _GetAttr(n, attr, defaultValue=None):
  for pair in n.attrs:
    if pair[0] == attr:
      return pair[1]
  return defaultValue

def _GetMapFunctionHrefFromPiReport(html_contents):
  soup = polymer_soup.PolymerSoup(html_contents)
  elements = soup.findAll('polymer-element')
  for element in elements:
    if _GetAttr(element, 'extends').lower() == 'pi-ui-pi-report':
      map_function_href = _GetAttr(element, 'map-function-href')
      if map_function_href is None:
        raise Exception('Report is missing map-function-href attribute')
      pi_report_element_name = _GetAttr(element, 'name', None)
      if pi_report_element_name is None:
        raise Exception('Report is missing name attribute')
      return map_function_href, pi_report_element_name
  raise Exception('No element that extends pi-ui-pi-report was found')


def PiReportToHTML(output_file, trace_directory, pi_report_file,
                   query, json_output=False,
                   stop_on_error=False, jobs=1):
  project = perf_insights_project.PerfInsightsProject()

  with open(pi_report_file, 'r') as f:
    pi_report_file_contents = f.read()

  map_function_href, pi_report_element_name = _GetMapFunctionHrefFromPiReport(
    pi_report_file_contents)
  map_file = project.GetAbsPathFromHRef(map_function_href)
  map_function_handle = map_function_handle_module.MapFunctionHandle(
      filename=map_file)

  if map_file == None:
    raise Exception('Could not find %s' % map_function_href)

  results = _MapTraces(trace_directory, map_function_handle,
                       query, stop_on_error, jobs)
  if stop_on_error and results.had_failures:
    sys.stderr.write('There were mapping errors. Aborting.');
    return 255

  with codecs.open(output_file, mode='w', encoding='utf-8') as ofile:
    if json_output:
      json.dump(results.AsDict(), ofile, indent=2)
    else:
      WriteResultsToFile(ofile, project,
                         pi_report_file, pi_report_element_name,
                         results)
  return 0


def _MapTraces(trace_directory, map_function_handle, query,
               stop_on_error=False,
               jobs=1):
  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(trace_directory)))

  trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
  runner = map_runner.MapRunner(trace_handles, map_function_handle,
                  stop_on_error=stop_on_error)
  return runner.Run(jobs=jobs)


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

  results_string = json.dumps(results.AsDict())

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
