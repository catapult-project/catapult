# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile

from telemetry.core import util


BASE_PROFILE_TYPES = ['clean', 'default']

PROFILE_TYPE_MAPPING = {
  'typical_user': 'chrome/test/data/extensions/profiles/content_scripts1',
  'power_user': 'chrome/test/data/extensions/profiles/extension_webrequest',
}

GENERATED_PROFILE_TYPES = []

def _GetFirstExistingBuildDir():
  # Look for the first build directory that exists, this is a bit weird because
  # if a developer machine has both Debug and Release build directories this
  # will return the first one, but on the bots this should not be an issue.
  chrome_root = util.GetChromiumSrcDir()
  for build_dir, build_type in util.GetBuildDirectories():
    candidate = os.path.join(chrome_root, build_dir, build_type)
    if os.path.isdir(candidate):
      return candidate
  return None

def GetGeneratedProfilesDir():
  build_directory = _GetFirstExistingBuildDir()
  if not build_directory:
    build_directory = tempfile.gettempdir()

  return os.path.abspath(os.path.join(build_directory, 'generated_profiles'))

def ScanForGeneratedProfiles():
  # It's illegal to call this function twice.
  assert not GENERATED_PROFILE_TYPES

  generated_profiles_dir = GetGeneratedProfilesDir()
  if not os.path.exists(generated_profiles_dir):
    return

  # Get list of subdirectories which are assumed to be generated profiles.
  subdirs = os.listdir(generated_profiles_dir)
  subdirs = filter(
      lambda d:os.path.isdir(os.path.join(generated_profiles_dir, d)), subdirs)

  # Make sure we don't have any conflics with hard coded profile names.
  hardcoded_profile_names = BASE_PROFILE_TYPES + PROFILE_TYPE_MAPPING.keys()
  for d in subdirs:
    if d in hardcoded_profile_names:
      raise Exception('Conflicting generated profile name: %s.' % d)

  GENERATED_PROFILE_TYPES.extend(subdirs)

def GetProfileTypes():
  """Returns a list of all command line options that can be specified for
  profile type."""
  return BASE_PROFILE_TYPES + PROFILE_TYPE_MAPPING.keys() + \
      GENERATED_PROFILE_TYPES

def GetProfileDir(profile_type):
  """Given a |profile_type| (as returned by GetProfileTypes()), return the
  directory to use for that profile or None if the profile doesn't need a
  profile directory (e.g. using the browser default profile).
  """
  if profile_type in BASE_PROFILE_TYPES:
    return None

  if profile_type in PROFILE_TYPE_MAPPING.keys():
    path = os.path.join(
      util.GetChromiumSrcDir(), *PROFILE_TYPE_MAPPING[profile_type].split('/'))
  else:
    # Generated profile.
    path = os.path.join(GetGeneratedProfilesDir(), profile_type)

  assert os.path.exists(path)
  return path
