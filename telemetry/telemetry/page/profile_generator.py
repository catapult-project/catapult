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

  if results.failures:
    logging.warning('Some pages failed.')
    logging.warning('Failed pages:\n%s',
                    '\n'.join(results.pages_that_had_failures))
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


def AddCommandLineArgs(parser):
  page_runner.AddCommandLineArgs(parser)

  profile_creators = _DiscoverProfileCreatorClasses().keys()
  legal_profile_creators = '|'.join(profile_creators)
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


def ProcessCommandLineArgs(parser, args):
  page_runner.ProcessCommandLineArgs(parser, args)

  if not args.profile_type_to_generate:
    parser.error("Must specify --profile-type-to-generate option.")

  profile_creators = _DiscoverProfileCreatorClasses().keys()
  if args.profile_type_to_generate not in profile_creators:
    legal_profile_creators = '|'.join(profile_creators)
    parser.error("Invalid profile type, legal values are: %s." %
        legal_profile_creators)

  if not args.browser_type:
    parser.error("Must specify --browser option.")

  if not args.output_dir:
    parser.error("Must specify --output-dir option.")

  if args.browser_options.dont_override_profile:
    parser.error("Can't use existing profile when generating profile.")


def Main():
  options = browser_options.BrowserFinderOptions()
  parser = options.CreateParser(
      "%%prog <--profile-type-to-generate=...> <--browser=...>"
      " <--output-directory>")
  AddCommandLineArgs(parser)
  _, _ = parser.parse_args()
  ProcessCommandLineArgs(parser, options)

  # Generate profile.
  profile_creators = _DiscoverProfileCreatorClasses()
  profile_creator_class = profile_creators[options.profile_type_to_generate]
  return GenerateProfiles(profile_creator_class,
      options.profile_type_to_generate, options)
