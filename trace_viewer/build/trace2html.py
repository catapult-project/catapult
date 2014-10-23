# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import gzip
import json
import optparse
import shutil
import os
import StringIO
import sys
import tempfile

from trace_viewer import trace_viewer_project
from tvcm import generate


def Main(args):
  parser = optparse.OptionParser(
    usage="%prog <options> trace_file1 [trace_file2 ...]",
    epilog="""Takes the provided trace file and produces a standalone html
file that contains both the trace and the trace viewer.""")
  parser.add_option(
      "--output", dest="output",
      help='Where to put the generated result. If not ' +
           'given, the trace filename is used, with an html suffix.')
  parser.add_option(
      "--quiet", action='store_true',
      help='Dont print the output file name')
  options, args = parser.parse_args(args)
  if len(args) == 0:
    parser.error('At least one trace file required')

  if options.output:
    output_filename = options.output
  elif len(args) > 1:
    parser.error('Must specify --output if >1 trace file')
  else:
    namepart = os.path.splitext(args[0])[0]
    output_filename = namepart + '.html'

  with open(output_filename, 'w') as f:
    WriteHTMLForTracesToFile(args, f)

  if not options.quiet:
    print output_filename
  return 0


class ViewerDataScript(generate.ExtraScript):
  def __init__(self, trace_data_string):
    super(ViewerDataScript, self).__init__()
    self._trace_data_string = trace_data_string

  def WriteToFile(self, output_file):
    output_file.write('<script id="viewer-data" type="application/json">\n')
    compressed_trace = StringIO.StringIO()
    with gzip.GzipFile(fileobj=compressed_trace, mode='w') as f:
      f.write(self._trace_data_string)
    b64_content = base64.b64encode(compressed_trace.getvalue())
    output_file.write(b64_content)
    output_file.write('\n</script>\n')


def WriteHTMLForTraceDataToFile(trace_data_list, title, output_file):
  project = trace_viewer_project.TraceViewerProject()
  load_sequence = project.CalcLoadSequenceForModuleNames(['build.trace2html'])
  scripts = [ViewerDataScript(json.dumps(trace_data)) for
             trace_data in trace_data_list]
  generate.GenerateStandaloneHTMLToFile(
    output_file, load_sequence, title, extra_scripts=scripts)


def WriteHTMLForTracesToFile(trace_filenames, output_file):
  trace_data_list = []
  for filename in trace_filenames:
    with open(filename, 'r') as f:
      trace_data_list.append(json.load(f))

  title = "Trace from %s" % ','.join(trace_filenames)
  WriteHTMLForTraceDataToFile(trace_data_list, title, output_file)
