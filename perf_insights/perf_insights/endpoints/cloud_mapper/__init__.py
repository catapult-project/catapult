# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys


# Directories in catapult/third_party required by cloud_mapper.
THIRD_PARTY_LIBRARIES = [
    'apiclient',
    'uritemplate',
]

# Directories in perf_insights/third_party required by cloud_mapper.
THIRD_PARTY_LIBRARIES_IN_PERF_INSIGHTS = [
    'cloudstorage',
]

# Libraries bundled with the App Engine SDK.
THIRD_PARTY_LIBRARIES_IN_SDK = [
    'httplib2',
    'oauth2client',
    'six',
]

# Files and directories in catapult/perf_insights/cloud_mapper.
CLOUD_MAPPER_FILES = [
    'appengine_config.py',
    'app.yaml',
    'remote_worker.yaml',
    'local_worker.yaml',
    'queue.yaml',
    'dispatch.yaml',
    'cron.yaml',
    'index.yaml',
    'Dockerfile',
    'perf_insights',
    'perf_insights_project.py',
]


def PathsForDeployment():
  """Returns a list of paths to things required for deployment.

  This list is used when building a temporary deployment directory;
  each of the items in this list will have a corresponding file or
  directory with the same basename in the deployment directory.
  """
  paths = []

  catapult_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__),
      os.path.pardir,
      os.path.pardir,
      os.path.pardir,
      os.path.pardir))
  cloud_mapper_dir = os.path.join(
      catapult_path, 'perf_insights')
  for name in CLOUD_MAPPER_FILES:
    paths.append(os.path.join(cloud_mapper_dir, name))

  try:
    import dev_appserver
  except ImportError:
    # The App Engine SDK is assumed to be in PYTHONPATH when setting
    # up the deployment directory, but isn't available in production.
    # (But this function shouldn't be called in production anyway.)
    sys.stderr.write('Error importing dev_appserver; please install app engine'
                     ' SDK. See https://cloud.google.com/appengine/downloads\n')
    sys.exit(1)
  for path in dev_appserver.EXTRA_PATHS:
    if os.path.basename(path) in THIRD_PARTY_LIBRARIES_IN_SDK:
      paths.append(path)

  third_party_dir = os.path.join(catapult_path, 'third_party')
  for library_dir in THIRD_PARTY_LIBRARIES:
    paths.append(os.path.join(third_party_dir, library_dir))

  third_party_dir = os.path.join(catapult_path, 'perf_insights', 'third_party')
  for library_dir in THIRD_PARTY_LIBRARIES_IN_PERF_INSIGHTS:
    paths.append(os.path.join(third_party_dir, library_dir))
  print paths

  return paths
