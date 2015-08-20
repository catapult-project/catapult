#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import tempfile

_CATAPULT_THIRD_PARTY = os.path.abspath(
  os.path.join(os.path.dirname(__file__), os.path.pardir, 'third_party'))


@contextlib.contextmanager
def TempDeploymentDir(app_dir):
  """Sets up and tears down a directory for deploying an app."""
  try:
    deployment_dir = tempfile.mkdtemp(prefix='deploy-')
    _PopulateDeploymentDir(app_dir, deployment_dir)
    yield deployment_dir
  finally:
    _CleanUp(deployment_dir)


def _PopulateDeploymentDir(app_dir, deployment_dir):
  """Fills the deployment directory with symlinks.

  This populates the deployment directory with only symlinks; this could
  potentially be made more flexible by taking as input the list of paths
  to make symlinks for.

  TODO(qyearsley): Later I think I'd like to add symlinks for all of
  the libraries in the app engine SDK lib/ directory, which would mean
  we could remove httplib2 and oauth2client from catapult/third_party/.
  """
  for name in os.listdir(app_dir):
    os.symlink(
        os.path.join(app_dir, name),
        os.path.join(deployment_dir, name))
  os.symlink(
      _CATAPULT_THIRD_PARTY,
      os.path.join(deployment_dir, 'third_party'))


def _CleanUp(deployment_dir):
  """Removes a directory that is populated with symlinks."""
  for symlink_name in os.listdir(deployment_dir):
    link_path = os.path.join(deployment_dir, symlink_name)
    if os.path.islink(link_path):
      os.unlink(link_path)
  os.rmdir(deployment_dir)

