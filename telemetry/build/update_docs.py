# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import optparse
import os
import pkgutil
import pydoc
import sys

from telemetry.core import util

def RemoveAllDocs(docs_dir):
  for dirname, _, filenames in os.walk(docs_dir):
    for filename in filenames:
      os.remove(os.path.join(dirname, filename))

def WriteDocsFor(module):
  pydoc.writedoc(module)
  for _, modname, _ in pkgutil.walk_packages(
      module.__path__, module.__name__ + '.'):
    if modname.endswith('_unittest'):
      logging.info("skipping %s due to being a unittest", modname)
      continue

    module = __import__(modname, fromlist=[""])
    name, _ = os.path.splitext(module.__file__)
    if not os.path.exists(name + '.py'):
      logging.info("skipping %s due to being an orphan .pyc", module.__file__)
      continue

    pydoc.writedoc(module)

def Main(args):
  parser = optparse.OptionParser()
  parser.add_option(
      '-v', '--verbose', action='count', default=0,
      help='Increase verbosity level (repeat as needed)')
  options, args = parser.parse_args(args)
  if options.verbose >= 2:
    logging.basicConfig(level=logging.DEBUG)
  elif options.verbose:
    logging.basicConfig(level=logging.INFO)
  else:
    logging.basicConfig(level=logging.WARNING)


  telemetry_dir = util.GetTelemetryDir()
  docs_dir = os.path.join(telemetry_dir, 'docs')

  assert os.path.isdir(docs_dir)

  RemoveAllDocs(docs_dir)

  if telemetry_dir not in sys.path:
    sys.path.append(telemetry_dir)
  import telemetry

  old_cwd = os.getcwd()
  try:
    os.chdir(docs_dir)
    WriteDocsFor(telemetry)
  finally:
    os.chdir(old_cwd)
