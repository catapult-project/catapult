# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.page import page_test


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

    test = self.test()
    ps = self.CreatePageSet(options)
    results = page_runner.Run(test, ps, options)
    results.PrintSummary()
    return len(results.failures) + len(results.errors)

  def CreatePageSet(self, options):  # pylint: disable=W0613
    """Get the page set this test will run on.

    By default, it will create a page set from the file at this test's
    page_set attribute. Override to generate a custom page set.
    """
    assert hasattr(self, 'page_set'), 'This test has no "page_set" attribute.'
    return page_set.PageSet.FromFile(self.page_set)
