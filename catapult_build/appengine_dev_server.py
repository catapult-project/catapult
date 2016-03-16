#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import sys

from catapult_build import module_finder
from catapult_build import temp_deployment_dir


def DevAppserver(paths, args):
  """Starts a dev server for an App Engine app.

  Args:
    paths: List of paths to files and directories that should be linked
        (or copied) in the deployment directory.
    args: List of additional arguments to pass to the dev server.
  """
  try:
    import dev_appserver  # pylint: disable=unused-variable
  except ImportError:
    # TODO(qyearsley): Put the App Engine SDK in the path with the
    # binary dependency manager.
    # See https://github.com/catapult-project/catapult/issues/2135
    print 'This script requires the App Engine SDK to be in PYTHONPATH.'
    sys.exit(1)
  with temp_deployment_dir.TempDeploymentDir(paths) as temp_dir:
    print 'Running dev server on "%s".' % temp_dir
    subprocess.call(
        [module_finder.FindModule('dev_appserver')] + args + [temp_dir]
    )
