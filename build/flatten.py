#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import os
import sys
import parse_deps
import StringIO

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))

def flatten_module_contents(filenames):
  out = StringIO.StringIO()
  load_sequence = parse_deps.calc_load_sequence(filenames, srcdir)

  flattened_module_names = ["'%s'" % module.name for module in load_sequence]
  out.write("    if (!window.FLATTENED) window.FLATTENED = {};\n")
  for module in load_sequence:
    out.write("    window.FLATTENED['%s'] = true;\n" % module.name);

  for module in load_sequence:
    out.write(module.contents)
    if module.contents[-1] != '\n':
      out.write('\n')
  return out.getvalue()

def flatten_style_sheet_contents(filenames):
  out = StringIO.StringIO()
  load_sequence = parse_deps.calc_load_sequence(filenames, srcdir)

  # Stylesheets should be sourced from topmsot in, not inner-out.
  load_sequence.reverse()

  for module in load_sequence:
    for style_sheet in module.style_sheets:
      out.write(style_sheet.contents)
      if style_sheet.contents[-1] != '\n':
        out.write('\n')
  return out.getvalue()

def main(argv):
  parser = optparse.OptionParser(usage="flatten filename1.js [filename2.js ...]",
                                 epilog="""
This is a low-level flattening tool. You probably are meaning to run
generate_standalone_timeline_view.py
""")

  parser.add_option("--css", dest="flatten_css", action="store_true", help="Outputs a flattened stylesheet.")
  options, args = parser.parse_args(argv[1:])

  if len(args) == 0:
    sys.stderr.write("Expected: filename or filenames to flatten\n")
    return 255

  if options.flatten_css:
    sys.stdout.write(flatten_style_sheet_contents(args))
  else:
    sys.stdout.write(flatten_module_contents(args))
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
