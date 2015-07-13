# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import optparse
import os
import sys

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing import tracing_project
from tvcm import generate


def Main(args):

  parser = optparse.OptionParser(
      usage="%prog <options>",
      epilog="""Produces a standalone html import that contains the
trace viewer.""")

  project = tracing_project.TracingProject()
  project.AddConfigNameOptionToParser(parser)

  parser.add_option('--no-min', dest='no_min', default=False,
                    action='store_true',
                    help='skip minification')
  parser.add_option('--report-sizes', dest='report_sizes', default=False,
                    action='store_true',
                    help='Explain what makes tracing big.')
  parser.add_option('--report-deps', dest='report_deps', default=False,
                    action='store_true',
                    help='Print a dot-formatted deps graph.')
  parser.add_option(
      "--output", dest="output",
      help='Where to put the generated result. If not ' +
           'given, $TRACING/tracing/bin/trace_viewer.html is used.')

  options, args = parser.parse_args(args)
  if len(args) != 0:
    parser.error('No arguments needed.')

  tracing_dir = os.path.relpath(
      os.path.join(os.path.dirname(__file__), '..', '..'))
  if options.output:
    output_filename = options.output
  else:
    output_filename = os.path.join(
        tracing_dir, 'tracing/bin/trace_viewer_%s.html' % options.config_name)

  with codecs.open(output_filename, 'w', encoding='utf-8') as f:
    WriteTraceViewer(
        f,
        config_name=options.config_name,
        minify=not options.no_min,
        report_sizes=options.report_sizes,
        report_deps=options.report_deps)

  return 0


def WriteTraceViewer(output_file,
                     config_name=None,
                     minify=False,
                     report_sizes=False,
                     report_deps=False,
                     output_html_head_and_body=True,
                     extra_search_paths=None,
                     extra_module_names_to_load=None):
  project = tracing_project.TracingProject()
  if extra_search_paths:
    for p in extra_search_paths:
      project.source_paths.append(p)
  if config_name is None:
    config_name = project.GetDefaultConfigName()

  module_names = [project.GetModuleNameForConfigName(config_name)]
  if extra_module_names_to_load:
    module_names += extra_module_names_to_load
  load_sequence = project.CalcLoadSequenceForModuleNames(
      module_names)

  if report_deps:
    sys.stdout.write(project.GetDepsGraphFromModuleNames(module_names))

  generate.GenerateStandaloneHTMLToFile(
      output_file, load_sequence,
      minify=minify, report_sizes=report_sizes,
      output_html_head_and_body=output_html_head_and_body)
