#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import optparse
import sys
import os
import re

import tvcm_stub
import tvcm

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
tvcm_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../third_party/tvcm"))
third_party_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../third_party"))

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

  load_sequence = tvcm.calc_load_sequence(
      ['tracing/standalone_timeline_view.js'], [src_dir], [third_party_dir])

  if options.js_file:
    with _sopen(options.js_file, 'w') as f:
      f.write(tvcm.generate_js(load_sequence))

  if options.css_file:
    with _sopen(options.css_file, 'w') as f:
      f.write(tvcm.generate_css(load_sequence))

  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
