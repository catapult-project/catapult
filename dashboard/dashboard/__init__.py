# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

_CATAPULT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..'))

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

  This includes both Python libraries that are required, and also
  other files, such as config files.

  This list is used when building a temporary deployment directory;
  each of the items in this list will have a corresponding file or
  directory with the same basename in the deployment directory.
  """
  paths = []
  paths.extend(_CatapultThirdPartyLibraryPaths())
  for p in _AllSdkThirdPartyLibraryPaths():
    if os.path.basename(p) in THIRD_PARTY_LIBRARIES_IN_SDK:
      paths.append(p)
  for name in DASHBOARD_FILES:
    paths.append(os.path.join(_CATAPULT_PATH, 'dashboard', name))
  return paths


def ExtraPythonLibraryPaths():
  """Returns a list of Python library paths required for dashboard tests."""
  paths = []
  paths.append(os.path.join(_CATAPULT_PATH, 'dashboard'))
  paths.extend(_AllSdkThirdPartyLibraryPaths())
  paths.extend(_CatapultThirdPartyLibraryPaths())
  return paths


def _AllSdkThirdPartyLibraryPaths():
  """Returns a list of all third party library paths from the SDK."""
  try:
    import dev_appserver
  except ImportError:
    # TODO(qyearsley): Put the App Engine SDK in the path with the
    # binary dependency manager.
    # https://github.com/catapult-project/catapult/issues/2135
    print 'This script requires the App Engine SDK to be in PYTHONPATH.'
    sys.exit(1)
  return dev_appserver.EXTRA_PATHS


def _CatapultThirdPartyLibraryPaths():
  """Returns a list of required third-party libraries in catapult."""
  paths = []
  for library in THIRD_PARTY_LIBRARIES:
    paths.append(os.path.join(_CATAPULT_PATH, 'third_party', library))
  return paths
