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

  project = trace_viewer_project.TraceViewerProject()
  project.AddConfigNameOptionToParser(parser)

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
    WriteHTMLForTracesToFile(args, f, config_name=options.config_name)

  if not options.quiet:
    print output_filename
  return 0


class ViewerDataScript(generate.ExtraScript):
  def __init__(self, trace_data_string, mime_type):
    super(ViewerDataScript, self).__init__()
    self._trace_data_string = trace_data_string
    self._mime_type = mime_type

  def WriteToFile(self, output_file):
    output_file.write('<script id="viewer-data" type="%s">\n' % self._mime_type)
    compressed_trace = StringIO.StringIO()
    with gzip.GzipFile(fileobj=compressed_trace, mode='w') as f:
      f.write(self._trace_data_string)
    b64_content = base64.b64encode(compressed_trace.getvalue())
    output_file.write(b64_content)
    output_file.write('\n</script>\n')


def WriteHTMLForTraceDataToFile(trace_data_list,
                                title, output_file,
                                config_name=None):
  project = trace_viewer_project.TraceViewerProject()

  if config_name == None:
    config_name = project.GetDefaultConfigName()

  modules = [
    'build.trace2html',
    'extras.importer.gzip_importer', # Must have this regardless of config.
    project.GetModuleNameForConfigName(config_name)
  ]

  load_sequence = project.CalcLoadSequenceForModuleNames(modules)

  scripts = []
  for trace_data in trace_data_list:
    # If the object was previously decoded from valid JSON data (e.g., in
    # WriteHTMLForTracesToFile), it will be a JSON object at this point and we
    # should re-serialize it into a string. Other types of data will be already
    # be strings.
    if not isinstance(trace_data, basestring):
      trace_data = json.dumps(trace_data)
      mime_type = 'application/json'
    else:
      mime_type = 'text/plain'
    scripts.append(ViewerDataScript(trace_data, mime_type))
  generate.GenerateStandaloneHTMLToFile(
    output_file, load_sequence, title, extra_scripts=scripts)


def WriteHTMLForTracesToFile(trace_filenames, output_file, config_name=None):
  trace_data_list = []
  for filename in trace_filenames:
    with open(filename, 'r') as f:
      trace_data = f.read()
      try:
        trace_data = json.loads(trace_data)
      except ValueError:
        pass
      trace_data_list.append(trace_data)

  title = "Trace from %s" % ','.join(trace_filenames)
  WriteHTMLForTraceDataToFile(trace_data_list, title, output_file, config_name)
