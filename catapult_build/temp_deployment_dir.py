#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import os
import shutil
import tempfile
import logging


@contextlib.contextmanager
def TempDeploymentDir(paths, use_symlinks=True, cleanup=True, reuse_path=None):
  """Sets up and tears down a directory for deploying an app."""
  if use_symlinks:
    link_func = os.symlink
  else:
    link_func = _Copy

  try:
    deployment_dir = None
    if reuse_path is not None:
      deployment_dir = reuse_path
      logging.info('Reusing path: %s', reuse_path)
    else:
      deployment_dir = tempfile.mkdtemp(prefix='deploy-')
      logging.info('Created path: %s', deployment_dir)
      _PopulateDeploymentDir(deployment_dir, paths, link_func)
    yield deployment_dir
  finally:
    if cleanup and reuse_path is not None:
      logging.info('Cleaning up: %s', deployment_dir)
      shutil.rmtree(deployment_dir)


def _Copy(src, dst):
  if os.path.isdir(src):
    shutil.copytree(src, dst)
  else:
    shutil.copy2(src, dst)


def _PopulateDeploymentDir(deployment_dir, paths, link_func):
  """Fills the deployment directory using the link_func specified."""
  for path in paths:
    destination = os.path.join(deployment_dir, os.path.basename(path))
    link_func(path, destination)
