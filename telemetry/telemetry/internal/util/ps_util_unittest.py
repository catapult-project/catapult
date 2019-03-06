# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import psutil  # pylint: disable=import-error
from telemetry.internal.util import ps_util


class PsUtilTest(unittest.TestCase):

  def testListAllSubprocesses_RaceCondition(self):
    """This is to check that crbug.com/934575 stays fixed."""
    class FakeProcess(object):
      def __init__(self):
        self.pid = '1234'
      def name(self):
        raise psutil.ZombieProcess('this is an error')
    output = ps_util._GetProcessDescription(FakeProcess())
    self.assertIn('ZombieProcess', output)
    self.assertIn('this is an error', output)
