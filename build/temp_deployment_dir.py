#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import tempfile


@contextlib.contextmanager
def TempDeploymentDir(paths):
  """Sets up and tears down a directory for deploying an app."""
  try:
    deployment_dir = tempfile.mkdtemp(prefix='deploy-')
    _PopulateDeploymentDir(deployment_dir, paths)
    yield deployment_dir
  finally:
    _CleanUp(deployment_dir)


def _PopulateDeploymentDir(deployment_dir, paths):
  """Fills the deployment directory with symlinks."""
  for path in paths:
    destination = os.path.join(deployment_dir, os.path.basename(path))
    os.symlink(path, destination)


def _CleanUp(deployment_dir):
  """Removes a directory that is populated with symlinks."""
  for symlink_name in os.listdir(deployment_dir):
    link_path = os.path.join(deployment_dir, symlink_name)
    if os.path.islink(link_path):
      os.unlink(link_path)
  os.rmdir(deployment_dir)

