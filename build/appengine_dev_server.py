#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys

from build import temp_deployment_dir


def DevAppserver(app_dir):
  """Starts a dev server for an App Engine app.

  Args:
    app_dir: Path of the directory that contains app.yaml.
  """
  try:
    import dev_appserver
  except ImportError:
    # TODO(qyearsley): Put the App Engine SDK in the path with the
    # binary dependency manager.
    print 'This script requires the App Engine SDK to be in PYTHONPATH.'
    sys.exit(1)
  with temp_deployment_dir.TempDeploymentDir(app_dir) as temp_dir:
    print 'Running dev server on "%s".' % temp_dir
    subprocess.call([
        dev_appserver.__file__,
        temp_dir,
    ])
