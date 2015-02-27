# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from telemetry.util import cloud_storage
from telemetry.util import find_dependencies


class FindDependenciesTest(unittest.TestCase):
  @unittest.skipUnless(
      cloud_storage.SupportsProdaccess(
          os.path.realpath(cloud_storage.FindGsutil())),
      'Could not find a depot_tools installation with gsutil.')
  def testGsutil(self):
    parser = optparse.OptionParser()
    find_dependencies.FindDependenciesCommand.AddCommandLineArgs(parser)
    options, _ = parser.parse_args([])

    try:
      temp_dir = tempfile.mkdtemp()
      zip_path = os.path.join(temp_dir, 'gsutil.zip')
      options.zip = zip_path

      find_dependencies.ZipDependencies([], set(), options)

      if platform.system() == 'Windows':
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
          zip_file.extractall(temp_dir)
      else:
        # Use unzip instead of Python zipfile to preserve file permissions.
        with open(os.devnull, 'w') as dev_null:
          subprocess.call(['unzip', zip_path], cwd=temp_dir, stdout=dev_null)
      third_party_path = os.path.join(temp_dir, 'telemetry', 'src', 'tools',
                                      'telemetry', 'third_party')
      # __init__.py is in Chromium src, but we didn't include any repo files.
      open(os.path.join(third_party_path, '__init__.py'), 'a').close()

      gsutil_path = os.path.join(third_party_path, 'gsutil', 'gsutil')
      self.assertTrue(os.access(gsutil_path, os.X_OK))

      with open(os.devnull, 'w') as dev_null:
        # gsutil with no args should print usage and exit with exit code 0.
        gsutil_command = [sys.executable, gsutil_path]
        self.assertEqual(subprocess.call(gsutil_command, stdout=dev_null), 0)

        # gsutil config should wait for the user and not exit with exit code 1.
        #gsutil_command = [sys.executable, gsutil_path, 'config',
        #                  '-o', os.path.join(temp_dir, 'config_file')]
        #gsutil_process = subprocess.Popen(gsutil_command, stdout=dev_null)
        #try:
        #  util.WaitFor(gsutil_process.poll, timeout=0.5)
        #  self.assertEqual(gsutil_process.returncode, 0,
        #                   msg='gsutil config failed.')
        #except exceptions.TimeoutException:
        #  gsutil_process.terminate()
        #  gsutil_process.wait()
    finally:
      shutil.rmtree(temp_dir)
