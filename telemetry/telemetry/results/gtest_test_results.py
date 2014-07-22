# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from telemetry.results import page_test_results


class GTestTestResults(page_test_results.PageTestResults):
  def __init__(self, output_stream):
    super(GTestTestResults, self).__init__(output_stream)
    self._timestamp = None

  def _GetMs(self):
    return (time.time() - self._timestamp) * 1000

  def _emitFailure(self, page, err):
    print >> self._output_stream, self._GetStringFromExcInfo(err)
    print >> self._output_stream, '[  FAILED  ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def AddValue(self, value):
    # TODO(chrishenry): When FailureValue is added, this should instead
    # validate that isinstance(value, FailureValue) is true.
    raise Exception('GTestTestResults does not support AddValue().')

  def AddFailure(self, page, err):
    super(GTestTestResults, self).AddFailure(page, err)
    self._emitFailure(page, err)

  def StartTest(self, page):
    super(GTestTestResults, self).StartTest(page)
    print >> self._output_stream, '[ RUN      ]', page.display_name
    self._output_stream.flush()
    self._timestamp = time.time()

  def AddSuccess(self, page):
    super(GTestTestResults, self).AddSuccess(page)
    print >> self._output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def AddSkip(self, page, reason):
    super(GTestTestResults, self).AddSkip(page, reason)
    logging.warning('===== SKIPPING TEST %s: %s =====',
                    page.display_name, reason)
    if self._timestamp == None:
      self._timestamp = time.time()
    print >> self._output_stream, '[       OK ]', page.display_name, (
        '(%0.f ms)' % self._GetMs())
    self._output_stream.flush()

  def PrintSummary(self):
    unit = 'test' if len(self.successes) == 1 else 'tests'
    print >> self._output_stream, '[  PASSED  ]', (
        '%d %s.' % (len(self.successes), unit))
    if self.failures:
      unit = 'test' if len(self.failures) == 1 else 'tests'
      print >> self._output_stream, '[  FAILED  ]', (
          '%d %s, listed below:' % (len(self.failures), unit))
      for page, _ in self.failures:
        print >> self._output_stream, '[  FAILED  ] ', (
            page.display_name)
      print >> self._output_stream
      count = len(self.failures)
      unit = 'TEST' if count == 1 else 'TESTS'
      print >> self._output_stream, '%d FAILED %s' % (count, unit)
    print >> self._output_stream
    self._output_stream.flush()
