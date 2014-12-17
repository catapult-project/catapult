# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import StringIO
import sys
import tempfile

from trace_viewer import trace_viewer_project
from tvcm import generate


def Main(args):

  parser = optparse.OptionParser(
    usage="%prog <options>",
    epilog="""Produces a standalone html import that contains the
trace viewer.""")

  project = trace_viewer_project.TraceViewerProject()
  project.AddConfigNameOptionToParser(parser)

  parser.add_option('--no-min', dest='no_min', default=False,
                    action='store_true',
                    help='skip minification')
  parser.add_option('--report-sizes', dest='report_sizes', default=False,
                    action='store_true',
                    help='Explain what makes trace_viewer big.')
  parser.add_option(
      "--output", dest="output",
      help='Where to put the generated result. If not ' +
           'given, $TRACE_VIEWER/bin/trace_viewer.html is used.')

  options, args = parser.parse_args(args)
  if len(args) != 0:
    parser.error('No arguments needed.')

  trace_viewer_dir = os.path.relpath(os.path.join(os.path.dirname(__file__), '..', '..'))
  if options.output:
    output_filename = options.output
  else:
    output_filename = os.path.join(
        trace_viewer_dir, 'bin/trace_viewer_%s.html' % options.config_name)

  with open(output_filename, 'w') as f:
    WriteTraceViewer(
        f,
        config_name=options.config_name,
        minify=not options.no_min,
        report_sizes=options.report_sizes)

  return 0


def WriteTraceViewer(output_file, config_name=None, minify=False, report_sizes=False):
  project = trace_viewer_project.TraceViewerProject()

  if config_name == None:
    config_name = project.GetDefaultConfigName()

  load_sequence = project.CalcLoadSequenceForModuleNames(
    ['trace_viewer', project.GetModuleNameForConfigName(config_name)])
  generate.GenerateStandaloneHTMLToFile(
    output_file, load_sequence, minify=minify, report_sizes=report_sizes)
