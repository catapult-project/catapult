# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform import android_sysfs_platform


class AndroidSysfsPlatformTest(unittest.TestCase):
  cstate = {
    'cpu0': 'C0\nC1\n103203424\n5342040\n300\n500\n1403232500',
    'cpu1': 'C0\n124361858\n300\n1403232500'
  }
  expected_cstate = {
    'cpu0': {
      'WFI': 103203424,
      'C0': 1403232391454536,
      'C1': 5342040
    },
    'cpu1': {
      'WFI': 124361858,
      'C0': 1403232375638142
    }
  }
  def testAndroidParseCpuStates(self):
    # Use mock start and end times to allow for the test to calculate C0.
    results = android_sysfs_platform.AndroidSysfsPlatform.ParseStateSample(
        self.cstate)
    for cpu in results:
      for state in results[cpu]:
        self.assertAlmostEqual(results[cpu][state],
                               self.expected_cstate[cpu][state])
