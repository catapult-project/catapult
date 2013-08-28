# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles generating profiles and transferring them to/from mobile devices."""

from telemetry.core import browser_options
from telemetry.page import page_runner

def GenerateProfiles():
  """Generate a profile"""
  raise Exception("create command unimplemented.")

def UploadProfiles():
  """Upload stored generated profiles to a mobile device for use by telemetry
  tests.
  """
  raise Exception("upload command unimplemented.")

def DownloadProfiles():
  """Download generated profiles from a mobile device for future use."""
  raise Exception("download command unimplemented.")

def Main():
  COMMANDS = [
    ('create', GenerateProfiles),
    ('upload', UploadProfiles),
    ('download', DownloadProfiles)
  ]

  LEGAL_COMMANDS = '|'.join([x[0] for x in COMMANDS])

  options = browser_options.BrowserOptions()
  parser = options.CreateParser("%%prog <%s> <--browser=...>" % LEGAL_COMMANDS)
  page_runner.AddCommandLineOptions(parser)

  _, args = parser.parse_args()

  if len(args) < 1:
    raise Exception("Must specify one of <%s>" % LEGAL_COMMANDS)

  if not options.browser_type:
    raise Exception("Must specify --browser option.")

  commands_dict = dict(COMMANDS)
  if args[0] not in commands_dict.keys():
    raise Exception("Unsupported command '%s', Valid options are "
        "%s" % (args[0], LEGAL_COMMANDS))
  commands_dict[args[0]]()

  return 0
