# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import sys

_CATAPULT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..'))

# Directories in catapult/third_party required by dashboard.
THIRD_PARTY_LIBRARIES = [
    'cloudstorage',
    'depot_tools',
    'flot',
    'gae_ts_mon',
    'jquery',
    'polymer',
    'polymer-svg-template',
    'polymer2/bower_components',
    'polymer2/bower_components/chopsui',
    'redux/redux.min.js',
]

# Add third party libraries needed *copying* for python 2. When running in
# python 3, those libraries should be installed either by pip or vpython.
THIRD_PARTY_LIBRARIES_PY2 = THIRD_PARTY_LIBRARIES + [
    'apiclient',
    'beautifulsoup4',
    'cachetools',
    'certifi',
    'chardet',
    'click',
    'flask',
    'google-auth',
    'graphy',
    'html5lib-python',
    'httplib2/python2/httplib2',
    'idna',
    'ijson',
    'itsdangerous',
    'jinja2',
    'mapreduce',
    'markupsafe',
    'mock',
    'oauth2client',
    'pipeline',
    'pyasn1',
    'pyasn1_modules',
    'pyparsing',
    'requests',
    'requests_toolbelt',
    'rsa',
    'six',
    'uritemplate',
    'urllib3',
    'webapp2',
    'webtest',
    'werkzeug',
]

THIRD_PARTY_LIBRARIES_PY3 = THIRD_PARTY_LIBRARIES

# Files and directories in catapult/dashboard.
DASHBOARD_FILES = [
    'api.yaml',
    'api-py3.yaml',  # remove after py3 migration is finalized.
    'app.yaml',
    'app-py3.yaml',  # remove after py3 migration is finalized.
    'appengine_config.py',
    'cron.yaml',
    'dashboard',
    'dispatch.yaml',
    'index.yaml',
    'pinpoint.yaml',
    'pinpoint-py3.yaml',  # remove after py3 migration is finalized.
    'queue.yaml',
    'requirements.txt',
    'scripts.yaml',
    'upload-processing.yaml',
    'upload-processing-py3.yaml',  # remove after py3 migration is finalized.
    'upload.yaml',
    'upload-py3.yaml',  # remove after py3 migration is finalized.
]

TRACING_PATHS = [
    'tracing/tracing',
    'tracing/tracing_build',
    'tracing/third_party/gl-matrix/dist/gl-matrix-min.js',
    'tracing/third_party/mannwhitneyu',
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
  for name in DASHBOARD_FILES:
    paths.append(os.path.join(_CATAPULT_PATH, 'dashboard', name))
  paths.append(os.path.join(_CATAPULT_PATH, 'tracing', 'tracing_project.py'))
  paths.append(os.path.join(_CATAPULT_PATH, 'common', 'py_utils', 'py_utils'))
  # Required by py_utils
  paths.append(os.path.join(_CATAPULT_PATH, 'devil', 'devil'))
  paths.extend(_TracingPaths())
  return paths


def PathsForTesting():
  """Returns a list of Python library paths required for dashboard tests."""
  return _AllSdkThirdPartyLibraryPaths() + _CatapultThirdPartyLibraryPaths() + [
      os.path.join(_CATAPULT_PATH, 'dashboard'),
      os.path.join(_CATAPULT_PATH, 'tracing'),
      os.path.join(_CATAPULT_PATH, 'common', 'py_utils', 'py_utils'),

      # Required by py_utils
      os.path.join(_CATAPULT_PATH, 'devil', 'devil'),

      # Isolate the sheriff_config package, since it's deployed independently.
      os.path.join(_CATAPULT_PATH, 'dashboard', 'dashboard', 'sheriff_config'),
  ]


def _AllSdkThirdPartyLibraryPaths():
  """Returns a list of all third party library paths from the SDK.

  The AppEngine documentation directs us to add App Engine libraries from the
  SDK to our Python path for local unit tests.
    https://cloud.google.com/appengine/docs/python/tools/localunittesting
  """
  paths = []
  for sdk_bin_path in os.environ['PATH'].split(os.pathsep):
    if 'google-cloud-sdk' not in sdk_bin_path:
      continue

    if not os.path.isdir(sdk_bin_path):
      sdk_bin_path = os.path.dirname(sdk_bin_path)

    appengine_path = os.path.join(sdk_bin_path, 'platform', 'google_appengine')
    paths.append(appengine_path)
    sys.path.insert(0, appengine_path)

  try:
    # pylint: disable=import-outside-toplevel
    if sys.version_info.major == 2:
      import dev_appserver
    else:
      # dev_appserver is not ready for python 3. Try import google.appengine
      # for validation purpose.
      import google.appengine  # pylint: disable=unused-import
  except ImportError:
    # TODO: Put the Cloud SDK in the path with the binary dependency manager.
    # https://github.com/catapult-project/catapult/issues/2135
    print('This script requires the Google Cloud SDK to be in PYTHONPATH.')
    print(
        'See https://chromium.googlesource.com/catapult/+/HEAD/dashboard/README.md'
    )
    sys.exit(1)

  if sys.version_info.major == 2:
    paths.extend(dev_appserver.EXTRA_PATHS)
  return paths


def _CatapultThirdPartyLibraryPaths():
  """Returns a list of required third-party libraries in catapult."""
  paths = []
  paths.append(
      os.path.join(_CATAPULT_PATH, 'common', 'node_runner', 'node_runner',
                   'node_modules', '@chopsui'))
  third_party_libraries = (
      THIRD_PARTY_LIBRARIES_PY3 if sys.version_info.major == 3
      else THIRD_PARTY_LIBRARIES_PY2)
  for library in third_party_libraries:
    paths.append(os.path.join(_CATAPULT_PATH, 'third_party', library))
  return paths


def _TracingPaths():
  """Returns a list of paths that may be imported from tracing."""
  # TODO(sullivan): This should either pull from tracing_project or be generated
  # via gypi. See https://github.com/catapult-project/catapult/issues/3048.
  paths = []
  for path in TRACING_PATHS:
    paths.append(os.path.join(_CATAPULT_PATH, os.path.normpath(path)))
  return paths
