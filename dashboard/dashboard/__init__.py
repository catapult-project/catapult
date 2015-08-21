# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


# Directories in catapult/third_party required by dashboard.
THIRD_PARTY_LIBRARIES = [
    'apiclient',
    'beautifulsoup4',
    'graphy',
    'mapreduce',
    'mock',
    'pipeline',
    'uritemplate',
    'webtest',
    'flot',
    'jquery',
    'polymer',
]

# Libraries bundled with the App Engine SDK.
THIRD_PARTY_LIBRARIES_IN_SDK = [
    'httplib2',
    'oauth2client',
    'six',
]

# Files and directories in catapult/dashboard.
DASHBOARD_FILES = [
    'appengine_config.py',
    'app.yaml',
    'dashboard',
    'index.yaml',
    'mapreduce.yaml',
    'queue.yaml',
]


def PathsForDeployment():
  """Returns a list of paths to things required for deployment.

  This list is used when building a temporary deployment directory;
  each of the items in this list will have a corresponding file or
  directory with the same basename in the deployment directory.
  """
  paths = []

  catapult_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), os.path.pardir, os.path.pardir))
  dashboard_dir = os.path.join(catapult_path, 'dashboard')
  for name in DASHBOARD_FILES:
    paths.append(os.path.join(dashboard_dir, name))

  try:
    import dev_appserver
  except ImportError:
    # The App Engine SDK is assumed to be in PYTHONPATH when setting
    # up the deployment directory, but isn't available in production.
    # (But this function shouldn't be called in production anyway.)
    pass
  for path in dev_appserver.EXTRA_PATHS:
    if os.path.basename(path) in THIRD_PARTY_LIBRARIES_IN_SDK:
      paths.append(path)

  third_party_dir = os.path.join(catapult_path, 'third_party')
  for library_dir in THIRD_PARTY_LIBRARIES:
    paths.append(os.path.join(third_party_dir, library_dir))

  return paths
