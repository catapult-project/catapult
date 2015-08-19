#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script uploads a version of the dashboard by creating a temp
# directory and making symlinks in it, then invoking appcfg.py.

# TODO(qyearsley): Add a step to vulcanize each template HTML file.
# TODO(qyearsley): Add a step to put static files in a versioned
# directory and modify app.yaml and request_handler as needed.

import appcfg
import argparse
import os
import subprocess
import tempfile


def _AppcfgUpdate(app_yaml_dir, appid='chromeperf'):
  subprocess.call([
      appcfg.__file__,
      '--application=%s' % appid,
      '--version=%s' % _VersionName(),
      'update',
      app_yaml_dir,
  ])


def _MakeDeploymentDir():
  dashboard = os.path.abspath(os.path.dirname(__file__))
  catapult_third_party = os.path.abspath(
      os.path.join(dashboard, os.path.pardir, 'third_party'))
  deployment_dir = tempfile.mkdtemp(prefix='deploy-')
  for name in os.listdir(dashboard):
    os.symlink(
        os.path.join(dashboard, name),
        os.path.join(deployment_dir, name))
  os.symlink(
      catapult_third_party,
      os.path.join(deployment_dir, 'third_party'))
  return deployment_dir


def _Cleanup(deployment_dir):
  for symlink_name in os.listdir(deployment_dir):
    link_path = os.path.join(deployment_dir, symlink_name)
    if os.path.islink(link_path):
      os.unlink(link_path)
  os.rmdir(deployment_dir)


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


def Main():
  parser = argparse.ArgumentParser(description='Build and deploy dashboard.')
  parser.add_argument('--appid', default='chromeperf')
  args = parser.parse_args()
  try:
    deployment_dir = _MakeDeploymentDir()
    print 'Deploying from "%s".' % deployment_dir
    _AppcfgUpdate(deployment_dir, appid=args.appid)
  finally:
    _Cleanup(deployment_dir)


if __name__ == '__main__':
  Main()
