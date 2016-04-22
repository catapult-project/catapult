# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest
import json

import mock

from telemetry import project_config
from telemetry.core import util
from telemetry.testing import browser_test_runner


class BrowserTestRunnerTest(unittest.TestCase):

  @mock.patch('telemetry.internal.util.binary_manager.InitDependencyManager')
  def testJsonOutputFormat(self, mockInitDependencyManager):
    options = browser_test_runner.TestRunOptions()
    config = project_config.ProjectConfig(
        top_level_dir=os.path.join(util.GetTelemetryDir(), 'examples'),
        client_configs=['a', 'b', 'c'],
        benchmark_dirs=[
            os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests')]
    )
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    temp_file_name = temp_file.name
    try:
      browser_test_runner.Run(
          config, options,
          ['SimpleTest',
           '--write-abbreviated-json-results-to=%s' % temp_file_name])
      mockInitDependencyManager.assert_called_with(['a', 'b', 'c'])
      with open(temp_file_name) as f:
        test_result = json.load(f)
      self.assertEquals(test_result['failures'], [
          'browser_tests.simple_numeric_test.SimpleTest.multiplier_simple_2',
          'browser_tests.simple_numeric_test.SimpleTest.add_1_and_2',
          'browser_tests.simple_numeric_test.SimpleTest.add_7_and_3',
          'browser_tests.simple_numeric_test.SimpleTest.testSimple'])
      self.assertEquals(test_result['valid'], True)
    finally:
      os.remove(temp_file_name)
