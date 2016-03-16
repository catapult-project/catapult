# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(qyearsley): Add a step to vulcanize each template HTML file.
# TODO(qyearsley): Add a step to put static files in a versioned
# directory and modify app.yaml and request_handler as needed.

import subprocess
import sys

from catapult_build import module_finder
from catapult_build import temp_deployment_dir


def AppcfgUpdate(paths, app_id):
  """Deploys a new version of an App Engine app from a temporary directory.

  Args:
    paths: List of paths to files and directories that should be linked
        (or copied) in the deployment directory.
    app_id: The application ID to use.
  """
  try:
    import appcfg  # pylint: disable=unused-variable
  except ImportError:
    # TODO(qyearsley): Put the App Engine SDK in the path with the
    # binary dependency manager.
    # See: https://github.com/catapult-project/catapult/issues/2135
    print 'This script requires the App Engine SDK to be in PYTHONPATH.'
    sys.exit(1)
  with temp_deployment_dir.TempDeploymentDir(
      paths, use_symlinks=False) as temp_dir:
    print 'Deploying from "%s".' % temp_dir
    _Run([
        module_finder.FindModule('appcfg'),
        '--application=%s' % app_id,
        '--version=%s' % _VersionName(),
        'update',
        temp_dir,
    ])


def _VersionName():
  is_synced = not _Run(['git', 'diff', 'master']).strip()
  deployment_type = 'clean' if is_synced else 'dev'
  email = _Run(['git', 'config', '--get', 'user.email'])
  username = email[0:email.find('@')]
  commit_hash = _Run(['git', 'rev-parse', '--short=8', 'HEAD']).strip()
  return '%s-%s-%s' % (deployment_type, username, commit_hash)


def _Run(command):
  proc = subprocess.Popen(command, stdout=subprocess.PIPE)
  output, _ = proc.communicate()
  return output
