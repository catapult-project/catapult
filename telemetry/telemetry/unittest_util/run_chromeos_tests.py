# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os

from telemetry.core import util
from telemetry.unittest_util import run_tests


def RunTestsForChromeOS(browser_type, unit_tests, perf_tests):
  stream = _LoggingOutputStream()
  error_string = ''

  if unit_tests:
    logging.info('Running telemetry unit tests with browser_type "%s".' %
                browser_type)
    ret = _RunOneSetOfTests(browser_type, 'telemetry', unit_tests, stream)
    if ret:
      error_string += 'The unit tests failed.\n'

  if perf_tests:
    logging.info('Running telemetry perf tests with browser_type "%s".' %
                browser_type)
    ret = _RunOneSetOfTests(browser_type, 'perf', perf_tests, stream)
    if ret:
      error_string = 'The perf tests failed.\n'

  return error_string


def _RunOneSetOfTests(browser_type, dir_name, tests, stream):
  top_level_dir = os.path.join(util.GetChromiumSrcDir(), 'tools', dir_name)
  args = ['--browser', browser_type,
          '--top-level-dir', top_level_dir,
          '--jobs', '1'] + tests
  return run_tests.RunTestsCommand.main(args, stream=stream)


class _LoggingOutputStream(object):

  def __init__(self):
    self._buffer = []

  def write(self, s):
    """Buffer a string write. Log it when we encounter a newline."""
    if '\n' in s:
      segments = s.split('\n')
      segments[0] = ''.join(self._buffer + [segments[0]])
      log_level = logging.getLogger().getEffectiveLevel()
      try:  # TODO(dtu): We need this because of crbug.com/394571
        logging.getLogger().setLevel(logging.INFO)
        for line in segments[:-1]:
          logging.info(line)
      finally:
        logging.getLogger().setLevel(log_level)
      self._buffer = [segments[-1]]
    else:
      self._buffer.append(s)

  def flush(self):  # pylint: disable=W0612
    pass
