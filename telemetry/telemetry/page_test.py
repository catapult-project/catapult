# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class Failure(Exception):
  """Exception that can be thrown from MultiPageBenchmark to indicate an
  undesired but designed-for problem."""
  pass

class PageTestResults(object):
  def __init__(self):
    self.page_failures = []

  def AddFailure(self, page, message, details):
    self.page_failures.append({'page': page,
                               'message': message,
                               'details': details})

class PageTest(object):
  """A class styled on unittest.TestCase for creating page-specific tests."""

  def __init__(self, test_method_name):
    self.options = None
    try:
      self._test_method = getattr(self, test_method_name)
    except AttributeError:
      raise ValueError, 'No such method %s.%s' % (
        self.__class_, test_method_name) # pylint: disable=E1101

  def AddOptions(self, parser):
    """Override to expose command-line options for this benchmark.

    The provided parser is an optparse.OptionParser instance and accepts all
    normal results. The parsed options are available in MeasurePage as
    self.options."""
    pass

  def CustomizeBrowserOptions(self, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  def SetUpBrowser(self, browser):
    """Override to customize the browser right after it has launched."""
    pass

  def Run(self, options, page, tab, results):
    self.options = options
    try:
      self._test_method(page, tab, results)
    finally:
      self.options = None
