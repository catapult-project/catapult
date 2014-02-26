# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import gzip
import optparse
import shutil
import sys
import tempfile
import os

from build import trace_viewer_project
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
  def __init__(self, filename):
    super(ViewerDataScript, self).__init__()
    self._filename = filename

  def WriteToFile(self, output_file):
    output_file.write('<script id="viewer-data" type="application/json">\n')

    with tempfile.NamedTemporaryFile() as compressed_file:
      gzfile = gzip.open(compressed_file.name, 'wb')
      with open(self._filename, 'r') as f:
        shutil.copyfileobj(f, gzfile)
      gzfile.close()

      with open(compressed_file.name, 'rb') as gzfile:
        b64_content = base64.b64encode(gzfile.read())
        output_file.write(b64_content)

    output_file.write('\n</script>\n')

def WriteHTMLForTracesToFile(trace_filenames, output_file):
  project = trace_viewer_project.TraceViewerProject()
  load_sequence = project.CalcLoadSequenceForModuleFilenames(
      ['tracing/standalone_timeline_view.js'])

  with open(os.path.join(os.path.dirname(__file__),
                         'trace2html.js'), 'r') as f:
    bootstrap_js = f.read()
  bootstrap_script = generate.ExtraScript(text_content=bootstrap_js)

  scripts = [bootstrap_script]
  scripts += [ViewerDataScript(x) for x in trace_filenames]

  title = "Trace from %s" % ','.join(trace_filenames)
  generate.GenerateStandaloneHTMLToFile(
      output_file, load_sequence, title, extra_scripts=scripts)
