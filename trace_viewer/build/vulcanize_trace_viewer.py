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
    output_filename = os.path.join(trace_viewer_dir, 'bin/trace_viewer.html')

  with open(output_filename, 'w') as f:
    WriteTraceViewer(f)

  return 0


def WriteTraceViewer(output_file):
  project = trace_viewer_project.TraceViewerProject()
  load_sequence = project.CalcLoadSequenceForModuleNames(['build.vulcanize_trace_viewer'])
  generate.GenerateStandaloneHTMLToFile(
    output_file, load_sequence)
