# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handles generating profiles and transferring them to/from mobile devices."""

import logging
import optparse
import os
import shutil
import sys
import tempfile

from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import util
from telemetry.page import page_runner
from telemetry.page import profile_creator
from telemetry.page import test_expectations


def _DiscoverProfileCreatorClasses():
  profile_creators_dir = os.path.abspath(os.path.join(util.GetBaseDir(),
      os.pardir, 'perf', 'profile_creators'))
  base_dir = os.path.abspath(os.path.join(profile_creators_dir, os.pardir))

  profile_creators_unfiltered = discover.DiscoverClasses(
      profile_creators_dir, base_dir, profile_creator.ProfileCreator)

  # Remove '_creator' suffix from keys.
  profile_creators = {}
  for test_name, test_class in profile_creators_unfiltered.iteritems():
    assert test_name.endswith('_creator')
    test_name = test_name[:-len('_creator')]
    profile_creators[test_name] = test_class
  return profile_creators

def GenerateProfiles(profile_creator_class, profile_creator_name, options):
  """Generate a profile"""
  expectations = test_expectations.TestExpectations()
  test = profile_creator_class()

  temp_output_directory = tempfile.mkdtemp()
  options.output_profile_path = temp_output_directory

  results = page_runner.Run(test, test.page_set, expectations, options)

  if results.errors or results.failures:
    logging.warning('Some pages failed.')
    if results.errors or results.failures:
      logging.warning('Failed pages:\n%s',
                      '\n'.join(zip(*results.errors + results.failures)[0]))
    return 1

  # Everything is a-ok, move results to final destination.
  generated_profiles_dir = os.path.abspath(options.output_dir)
  if not os.path.exists(generated_profiles_dir):
    os.makedirs(generated_profiles_dir)
  out_path = os.path.join(generated_profiles_dir, profile_creator_name)
  if os.path.exists(out_path):
    shutil.rmtree(out_path)

  # A profile may contain pseudo files like sockets which can't be copied
  # around by bots.
  def IsPseudoFile(directory, paths):
    ignore_list = []
    for path in paths:
      full_path = os.path.join(directory, path)
      if (not os.path.isfile(full_path) and
          not os.path.isdir(full_path) and
          not os.path.islink(full_path)):
        logging.warning('Ignoring pseudo file: %s' % full_path)
        ignore_list.append(path)
    return ignore_list
  shutil.copytree(temp_output_directory, out_path, ignore=IsPseudoFile)
  shutil.rmtree(temp_output_directory)
  sys.stderr.write("SUCCESS: Generated profile copied to: '%s'.\n" % out_path)

  return 0

def Main():
  profile_creators = _DiscoverProfileCreatorClasses()
  legal_profile_creators = '|'.join(profile_creators.keys())

  options = browser_options.BrowserFinderOptions()
  parser = options.CreateParser(
      "%%prog <--profile-type-to-generate=...> <--browser=...>"
      " <--output-directory>")
  page_runner.AddCommandLineOptions(parser)

  group = optparse.OptionGroup(parser, 'Profile generation options')
  group.add_option('--profile-type-to-generate',
      dest='profile_type_to_generate',
      default=None,
      help='Type of profile to generate. '
           'Supported values: %s' % legal_profile_creators)
  group.add_option('--output-dir',
      dest='output_dir',
      help='Generated profile is placed in this directory.')
  parser.add_option_group(group)

  _, _ = parser.parse_args()

  # Sanity check arguments.
  if not options.profile_type_to_generate:
    raise Exception("Must specify --profile-type-to-generate option.")

  if options.profile_type_to_generate not in profile_creators.keys():
    raise Exception("Invalid profile type, legal values are: %s." %
        legal_profile_creators)

  if not options.browser_type:
    raise Exception("Must specify --browser option.")

  if not options.output_dir:
    raise Exception("Must specify --output-dir option.")

  if options.browser_options.dont_override_profile:
    raise Exception("Can't use existing profile when generating profile.")

  # Generate profile.
  profile_creator_class = profile_creators[options.profile_type_to_generate]
  return GenerateProfiles(profile_creator_class,
      options.profile_type_to_generate, options)
