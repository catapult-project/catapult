# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(qyearsley): Add a step to vulcanize each template HTML file.
# TODO(qyearsley): Add a step to put static files in a versioned
# directory and modify app.yaml and request_handler as needed.

import os
import subprocess
import sys

from catapult_build import temp_deployment_dir


def AppcfgUpdate(paths, app_id, service_name=None):
  """Deploys a new version of an App Engine app from a temporary directory.

  Args:
    paths: List of paths to files and directories that should be linked
        (or copied) in the deployment directory.
    app_id: The application ID to use.
  """
  with temp_deployment_dir.TempDeploymentDir(
      paths, use_symlinks=False) as temp_dir:
    print 'Deploying from "%s".' % temp_dir

    script_path = _FindScriptInPath('appcfg.py')
    if not script_path:
      print 'This script requires the App Engine SDK to be in PATH.'
      sys.exit(1)

    subprocess.call([
        sys.executable,
        script_path,
        '--application=%s' % app_id,
        '--version=%s' % _VersionName(),
        'update',
        os.path.join(temp_dir, service_name) if service_name else temp_dir,
    ])


def _FindScriptInPath(script_name):
  for path in os.environ['PATH'].split(os.pathsep):
    script_path = os.path.join(path, script_name)
    if os.path.exists(script_path):
      return script_path

  return None


def _VersionName():
  is_synced = not _Run(['git', 'diff', 'master', '--no-ext-diff']).strip()
  deployment_type = 'clean' if is_synced else 'dev'
  email = _Run(['git', 'config', '--get', 'user.email'])
  username = email[0:email.find('@')]
  commit_hash = _Run(['git', 'rev-parse', '--short=8', 'HEAD']).strip()
  return '%s-%s-%s' % (deployment_type, username, commit_hash)


def _Run(command):
  proc = subprocess.Popen(command, stdout=subprocess.PIPE)
  output, _ = proc.communicate()
  return output
