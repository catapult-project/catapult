# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys

import tvcm
from trace_viewer import trace_viewer_project

def GenerateHTML(outdir, load_sequence):
  return tvcm.GenerateStandaloneHTMLAsString(
    load_sequence,
    title='chrome://tracing',
    flattened_js_url='tracing.js')

def GenerateJS(outdir, load_sequence):
  return tvcm.GenerateJS(
    load_sequence,
    include_html_templates=False,
    use_include_tags_for_scripts=True,
    dir_for_include_tag_root=outdir)

def main(args):
  parser = optparse.OptionParser(usage="%prog --outdir=<directory>")
  parser.add_option("--outdir", dest="out_dir",
                    help="Where to place generated content")
  options, args = parser.parse_args(args)

  if not options.out_dir:
    sys.stderr.write("ERROR: Must specify --outdir=<directory>")
    parser.print_help()
    return 1

  filenames = ["tvcm/__init__.js", "about_tracing/__init__.js"]
  project = trace_viewer_project.TraceViewerProject()
  load_sequence = project.CalcLoadSequenceForModuleFilenames(filenames)

  olddir = os.getcwd()
  try:
    try:
      result_html = GenerateHTML(options.out_dir, load_sequence)
    except tvcm.module.DepsException, ex:
      sys.stderr.write("Error: %s\n\n" % str(ex))
      return 255

    o = open(os.path.join(options.out_dir, "about_tracing.html"), 'w')
    o.write(result_html)
    o.close()

    result_js = GenerateJS(options.out_dir, load_sequence)
    o = open(os.path.join(options.out_dir, "about_tracing.js"), 'w')
    o.write(result_js)
    o.close()

  finally:
    os.chdir(olddir)

  return 0
