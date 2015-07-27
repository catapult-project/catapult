# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import optparse
import os
import sys

import tvcm

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing import tracing_project


def main(args):
  parser = optparse.OptionParser(usage="%prog --outdir=<directory>")
  parser.add_option("--outdir", dest="out_dir",
                    help="Where to place generated content")
  parser.add_option('--no-min', dest='no_min', default=False,
                    action='store_true',
                    help='skip minification')
  options, args = parser.parse_args(args)

  if not options.out_dir:
    sys.stderr.write("ERROR: Must specify --outdir=<directory>")
    parser.print_help()
    return 1

  names = ["ui.extras.about_tracing.about_tracing"]
  project = tracing_project.TracingProject()
  load_sequence = project.CalcLoadSequenceForModuleNames(names)

  olddir = os.getcwd()
  try:
    if not os.path.exists(options.out_dir):
      os.makedirs(options.out_dir)
    o = codecs.open(os.path.join(options.out_dir, "about_tracing.html"), 'w',
                    encoding='utf-8')
    try:
      tvcm.GenerateStandaloneHTMLToFile(
          o,
          load_sequence,
          title='chrome://tracing',
          flattened_js_url='tracing.js',
          minify=not options.no_min)
    except tvcm.module.DepsException, ex:
      sys.stderr.write("Error: %s\n\n" % str(ex))
      return 255
    o.close()

    o = codecs.open(os.path.join(options.out_dir, "about_tracing.js"), 'w',
                    encoding='utf-8')
    assert o.encoding == 'utf-8'
    tvcm.GenerateJSToFile(
        o,
        load_sequence,
        use_include_tags_for_scripts=False,
        dir_for_include_tag_root=options.out_dir,
        minify=not options.no_min)
    o.close()

  finally:
    os.chdir(olddir)

  return 0
