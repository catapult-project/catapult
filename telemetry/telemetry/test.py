# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from telemetry.core import repeat_options
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import test_expectations


def GetBaseDir():
  main_module = sys.modules['__main__']
  if hasattr(main_module, '__file__'):
    return os.path.dirname(os.path.abspath(main_module.__file__))
  else:
    return os.getcwd()


class Test(object):
  """Base class for a Telemetry test or benchmark.

  A test packages a PageTest/PageMeasurement and a PageSet together.
  """
  options = {}
  enabled = True

  def Run(self, options):
    """Run this test with the given options."""
    assert hasattr(self, 'test'), 'This test has no "test" attribute.'
    assert issubclass(self.test, page_test.PageTest), (
            '"%s" is not a PageTest.' % self.test.__name__)

    for key, value in self.options.iteritems():
      setattr(options, key, value)

    options.repeat_options = self._CreateRepeatOptions(options)

    test = self.test()
    ps = self.CreatePageSet(options)
    expectations = self.CreateExpectations(ps)
    results = page_runner.Run(test, ps, expectations, options)
    results.PrintSummary()
    return len(results.failures) + len(results.errors)

  def _CreateRepeatOptions(self, options):
    return repeat_options.RepeatOptions(
        getattr(options, 'page_repeat_secs', None),
        getattr(options, 'pageset_repeat_secs', None),
        getattr(options, 'page_repeat_iters', 1),
        getattr(options, 'pageset_repeat_iters', 1),
      )

  def CreatePageSet(self, options):  # pylint: disable=W0613
    """Get the page set this test will run on.

    By default, it will create a page set from the file at this test's
    page_set attribute. Override to generate a custom page set.
    """
    assert hasattr(self, 'page_set'), 'This test has no "page_set" attribute.'
    return page_set.PageSet.FromFile(os.path.join(GetBaseDir(), self.page_set))

  def CreateExpectations(self, ps):  # pylint: disable=W0613
    """Get the expectations this test will run with.

    By default, it will create an empty expectations set. Override to generate
    custom expectations.
    """
    if hasattr(self, 'expectations'):
      return self.expectations
    else:
      return test_expectations.TestExpectations()
