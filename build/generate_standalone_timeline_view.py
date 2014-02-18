# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import optparse
import sys
import os
import re

import tvcm
from build import trace_viewer_project
def _sopen(filename, mode):
  if filename != '-':
    return open(filename, mode)
  return os.fdopen(os.dup(sys.stdout.fileno()), 'w')

def main(args):
  parser = optparse.OptionParser(
    usage="%prog --js=<filename> --css=<filename>",
    epilog="""
A script to takes all of the javascript and css files that comprise trace-viewer
and merges them together into two giant js and css files, taking into account
various ordering restrictions between them.
""")
  parser.add_option("--js", dest="js_file",
                    help="Where to place generated javascript file")
  parser.add_option("--css", dest="css_file",
                    help="Where to place generated css file")
  options, args = parser.parse_args(args)

  if not options.js_file and not options.css_file:
    sys.stderr.write("ERROR: Must specify one of --js=<filename> or "
        "--css=<filename>\n\n")
    parser.print_help()
    return 1

  project = trace_viewer_project.TraceViewerProject()
  load_sequence = tvcm.CalcLoadSequence(
      ['tracing/standalone_timeline_view.js'], project)

  if options.js_file:
    with _sopen(options.js_file, 'w') as f:
      f.write(tvcm.GenerateJS(load_sequence))

  if options.css_file:
    with _sopen(options.css_file, 'w') as f:
      f.write(tvcm.GenerateCSS(load_sequence))

  return 0
