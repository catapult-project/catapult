# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A tool to run long running tasks.

This allows a task to run in Task Queue which gives about 10 minutes execution
time.

Usage:

In https://chromeperf.appspot.com/_ah/stats/shell, pass a function to
task_runner.Run.  Task function should be picklable and must include any
required imports within the function's body.

Example:

  from dashboard import task_runner

  def unique_test_suite_names():
    from dashboard.models import graph_data
    query = graph_data.Test.query(graph_data.Test.parent_test == None)
    test_keys = query.fetch(limit=50000, keys_only=True)
    return sorted(set(k.string_id() for k in test_keys))

  task_runner.Run(unique_test_suite_names)

The task function return value and stdouts will be displayed at:
    https://chromeperf.appspot.com/get_logs?namespace=task_runner&name=report

WARNING:
Running code in Appstats does affect live dashboard.  So watchout for any
datastore writes that may corrupt or unintentionally delete data.
"""

import datetime
import marshal
import cStringIO
import sys
import time
import types

from google.appengine.ext import deferred

from dashboard import quick_logger

_TASK_QUEUE_NAME = 'task-runner-queue'

_REPORT_TEMPLATE = """%(function_name)s: %(start_time)s
 Stdout:
 %(stdout)s

 Elapsed: %(elapsed_time)f seconds.
 Returned results:
 %(returned_results)s
"""


def Run(task_function):
  """Runs task in task queue."""
  # Since defer uses pickle and pickle can't serialize non-global function,
  # we'll use marshal to serialize and deserialize the function code object
  # before and after defer.
  code_string = marshal.dumps(task_function.func_code)
  deferred.defer(_TaskWrapper, code_string, task_function.__name__,
                 _queue=_TASK_QUEUE_NAME)


def _TaskWrapper(code_string, function_name):
  """Runs the task and captures the stdout and the returned results."""
  formatted_start_time = datetime.datetime.now().strftime(
      '%Y-%m-%d %H:%M:%S %Z')
  _AddReportToLog('Starting task "%s" at %s.' %
                  (function_name, formatted_start_time))

  code = marshal.loads(code_string)
  task_function = types.FunctionType(code, globals(), 'TaskFunction')

  stdout_original = sys.stdout
  sys.stdout = stream = cStringIO.StringIO()
  start_time = time.time()
  try:
    returned_results = task_function()
  except Exception as e:  # Intentionally broad -- pylint: disable=broad-except
    print str(e)
    returned_results = ''
  elapsed_time = time.time() - start_time
  stdout = stream.getvalue()
  sys.stdout = stdout_original

  results = {
      'function_name': function_name,
      'start_time': formatted_start_time,
      'stdout': stdout,
      'returned_results': returned_results,
      'elapsed_time': elapsed_time
  }
  _AddReportToLog(_REPORT_TEMPLATE % results)


def _AddReportToLog(report):
  """Adds a log for bench results."""
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('task_runner', 'report', formatter)
  logger.Log(report)
  logger.Save()
