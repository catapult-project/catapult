# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import argparse
import os
import sys

import tracing_project
from py_vulcanize import generate


def Main(argv):

  parser = argparse.ArgumentParser(
      usage='%(prog)s <options>',
      epilog=('Produces a standalone HTML import that contains the\n'
              'trace viewer.'))

  project = tracing_project.TracingProject()
  project.AddConfigNameOptionToParser(parser)

  parser.add_argument('--no-min', default=False, action='store_true',
                      help='skip minification')
  parser.add_argument('--report-sizes', default=False, action='store_true',
                      help='Explain what makes tracing big.')
  parser.add_argument('--report-deps', default=False, action='store_true',
                      help='Print a dot-formatted deps graph.')
  parser.add_argument('--output',
                      help='Where to put the generated result. If not given, '
                           '$TRACING/tracing/bin/trace_viewer.html is used.')

  args = parser.parse_args(argv[1:])

  tracing_dir = os.path.relpath(
      os.path.join(os.path.dirname(__file__), '..', '..'))
  if args.output:
    output_filename = args.output
  else:
    output_filename = os.path.join(
        tracing_dir, 'tracing/bin/trace_viewer_%s.html' % args.config_name)

  with codecs.open(output_filename, 'w', encoding='utf-8') as f:
    WriteTraceViewer(
        f,
        config_name=args.config_name,
        minify=not args.no_min,
        report_sizes=args.report_sizes,
        report_deps=args.report_deps)

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

  vulcanizer = project.CreateVulcanizer()
  load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(
      module_names)

  if report_deps:
    sys.stdout.write(vulcanizer.GetDepsGraphFromModuleNames(module_names))

  generate.GenerateStandaloneHTMLToFile(
      output_file, load_sequence,
      minify=minify, report_sizes=report_sizes,
      output_html_head_and_body=output_html_head_and_body)
