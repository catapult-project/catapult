# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import quick_logger
from dashboard import testing_common


class QuickLoggerTest(testing_common.TestCase):

  def testQuickLogger_SaveAndGetNewLogEntry(self):
    template = '{message}{extra}'
    formatter = quick_logger.Formatter(template, extra='!')
    logger = quick_logger.QuickLogger('a_namespace', 'a_log_name', formatter)
    logger.Log('Hello world')
    logger.Save()
    logs = quick_logger.Get('a_namespace', 'a_log_name')
    self.assertEqual(len(logs), 1)
    self.assertEqual(logs[0].message, 'Hello world!')

  def testQuickLogger_LogSizeAndNumberAtSizeLimit(self):
    logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    for i in xrange(quick_logger._MAX_NUM_RECORD):
      logger.Log(str(i % 2) * quick_logger._MAX_MSG_SIZE)
    logger.Save()
    logs = quick_logger.Get('a_namespace', 'a_log_name')
    self.assertEqual(len(logs), quick_logger._MAX_NUM_RECORD)

  def testQuickLogger_MultipleLogs_UsesCorrectOrder(self):
    logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    for i in xrange(quick_logger._MAX_NUM_RECORD + 10):
      logger.Log(i)
    logger.Save()
    logs = quick_logger.Get('a_namespace', 'a_log_name')
    self.assertEqual(len(logs), quick_logger._MAX_NUM_RECORD)
    # First record is the last log added.
    self.assertEqual(logs[0].message, str(quick_logger._MAX_NUM_RECORD + 9))

  def testQuickLogger_LoggingWithId_UpdatesExistingLog(self):
    logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    first_id = logger.Log('First message.')
    logger.Log('Second message.')
    logger.Log('Third message.')
    logger.Save()

    logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    logger.Log('Updated first message.', first_id)
    logger.Save()

    logs = quick_logger.Get('a_namespace', 'a_log_name')
    self.assertEqual(3, len(logs))
    self.assertEqual('Updated first message.', logs[0].message)
    self.assertEqual('Third message.', logs[1].message)
    self.assertEqual('Second message.', logs[2].message)

  def testQuickLogger_MultipleLogs_RecordIsUnique(self):
    first_logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    second_logger = quick_logger.QuickLogger('a_namespace', 'a_log_name')
    first_id = first_logger.Log('First message.')
    second_id = second_logger.Log('Second message.')
    self.assertNotEqual(first_id, second_id)


if __name__ == '__main__':
  unittest.main()
