#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import calcdeps
import sys
import StringIO

def flatten_module_contents(filenames):
  out = StringIO.StringIO()
  load_sequence = calcdeps.calc_load_sequence(filenames)

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
  load_sequence = calcdeps.calc_load_sequence(filenames)

  # Stylesheets should be sourced from topmsot in, not inner-out.
  load_sequence.reverse()

  for module in load_sequence:
    for style_sheet in module.style_sheets:
      out.write(style_sheet.contents)
      if style_sheet.contents[-1] != '\n':
        out.write('\n')
  return out.getvalue()

def main(argv):
  parser = optparse.OptionParser(usage="flatten filename1.js [filename2.js ...]")
  parser.add_option("--css", dest="flatten_css", action="store_true", help="Outputs a flattened stylesheet.")
  options, args = parser.parse_args(argv)

  if options.flatten_css:
    sys.stdout.write(flatten_style_sheet_contents(args))
  else:
    sys.stdout.write(flatten_module_contents(args))
  return 255

if __name__ == "__main__":
  sys.exit(main(sys.argv))
