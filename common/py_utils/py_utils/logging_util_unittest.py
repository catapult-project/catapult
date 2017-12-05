# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import StringIO
import unittest

from py_utils import logging_util


class LoggingUtilTest(unittest.TestCase):
  def testCapture(self):
    s = StringIO.StringIO()
    with logging_util.CaptureLogs(s):
      logging.fatal('test')

    self.assertEqual(s.getvalue(), 'test\n')


if __name__ == '__main__':
  unittest.main()
