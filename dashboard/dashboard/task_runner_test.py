# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from dashboard import task_runner
from dashboard import testing_common


class TaskRunnerTest(testing_common.TestCase):

  def setUp(self):
    super(TaskRunnerTest, self).setUp()

  def _GetMockCallArg(self, function_mock, call_index):
    """Gets the first argument value for the call at |call_index|.

    Args:
      function_mock: A Mock object.
      call_index: The index at which the mocked function was called.

    Returns:
      The first argument value.
    """
    # See http://www.voidspace.org.uk/python/mock/helpers.html#call and
    # http://www.voidspace.org.uk/python/mock/mock.html#mock.Mock.call_args_list
    call_args_list = function_mock.call_args_list
    if not call_args_list or len(call_args_list) <= call_index:
      return None
    args, _ = call_args_list[call_index]
    return args[0]

  @mock.patch.object(task_runner, '_AddReportToLog')
  def testRun(self, add_report_to_log_mock):
    def SampleTask():
      print 'square root of 16'
      return 16 ** (1 / 2.0)

    task_runner.Run(SampleTask)

    self.ExecuteDeferredTasks(task_runner._TASK_QUEUE_NAME)

    call_arg = self._GetMockCallArg(add_report_to_log_mock, 1)
    self.assertIn('4.0', call_arg)
    self.assertIn('square root of 16', call_arg)
