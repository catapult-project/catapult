# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import exceptions
from telemetry.core import util
from telemetry.page import page_runner
from telemetry.page import page as page_module
from telemetry.page import page_set as page_set_module
from telemetry.page import page_test
from telemetry.page import test_expectations
from telemetry.unittest import options_for_unittests


class BasicTestPage(page_module.Page):
  def __init__(self, url, page_set, base_dir):
    super(BasicTestPage, self).__init__(url, page_set, base_dir)

  def RunSmoothness(self, action_runner):
    interaction = action_runner.BeginGestureInteraction(
        'ScrollAction', is_smooth=True)
    action_runner.ScrollPage()
    interaction.End()


class PageMeasurementUnitTestBase(unittest.TestCase):
  """unittest.TestCase-derived class to help in the construction of unit tests
  for a measurement."""

  def CreatePageSetFromFileInUnittestDataDir(self, test_filename):
    ps = self.CreateEmptyPageSet()
    page = BasicTestPage('file://' + test_filename, ps, base_dir=ps.base_dir)
    ps.AddPage(page)
    return ps

  def CreateEmptyPageSet(self):
    base_dir = util.GetUnittestDataDir()
    ps = page_set_module.PageSet(file_path=base_dir)
    return ps

  def RunMeasurement(self, measurement, ps,
      expectations=test_expectations.TestExpectations(),
      options=None):
    """Runs a measurement against a pageset, returning the rows its outputs."""
    if options is None:
      options = options_for_unittests.GetCopy()
    assert options
    temp_parser = options.CreateParser()
    page_runner.AddCommandLineArgs(temp_parser)
    measurement.AddCommandLineArgs(temp_parser)
    measurement.SetArgumentDefaults(temp_parser)
    defaults = temp_parser.get_default_values()
    for k, v in defaults.__dict__.items():
      if hasattr(options, k):
        continue
      setattr(options, k, v)

    measurement.CustomizeBrowserOptions(options.browser_options)
    options.output_file = None
    options.output_format = 'none'
    options.output_trace_tag = None
    page_runner.ProcessCommandLineArgs(temp_parser, options)
    measurement.ProcessCommandLineArgs(temp_parser, options)
    return page_runner.Run(measurement, ps, expectations, options)

  def TestTracingCleanedUp(self, measurement_class, options=None):
    ps = self.CreatePageSetFromFileInUnittestDataDir('blank.html')
    start_tracing_called = [False]
    stop_tracing_called = [False]

    class BuggyMeasurement(measurement_class):
      def __init__(self, *args, **kwargs):
        measurement_class.__init__(self, *args, **kwargs)

      # Inject fake tracing methods to browser
      def TabForPage(self, page, browser):
        ActualStartTracing = browser.StartTracing
        def FakeStartTracing(*args, **kwargs):
          ActualStartTracing(*args, **kwargs)
          start_tracing_called[0] = True
          raise exceptions.IntentionalException
        browser.StartTracing = FakeStartTracing

        ActualStopTracing = browser.StopTracing
        def FakeStopTracing(*args, **kwargs):
          ActualStopTracing(*args, **kwargs)
          stop_tracing_called[0] = True
        browser.StopTracing = FakeStopTracing

        return measurement_class.TabForPage(self, page, browser)

    measurement = BuggyMeasurement()
    try:
      self.RunMeasurement(measurement, ps, options=options)
    except page_test.TestNotSupportedOnPlatformFailure:
      pass
    if start_tracing_called[0]:
      self.assertTrue(stop_tracing_called[0])
