# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import sys

from telemetry import decorators
from telemetry.internal import story_runner
from telemetry.internal.util import command_line
from telemetry.page import legacy_page_test
from telemetry.story import expectations as expectations_module
from telemetry.story import typ_expectations
from telemetry.web_perf import story_test
from telemetry.web_perf import timeline_based_measurement
from tracing.value.diagnostics import generic_set

Info = decorators.Info

# TODO(crbug.com/859524): remove this once we update all the benchmarks in
# tools/perf to use Info decorator.
Owner = decorators.Info # pylint: disable=invalid-name


class InvalidOptionsError(Exception):
  """Raised for invalid benchmark options."""
  pass


class Benchmark(command_line.Command):
  """Base class for a Telemetry benchmark.

  A benchmark packages a measurement and a PageSet together.
  Benchmarks default to using TBM unless you override the value of
  Benchmark.test, or override the CreatePageTest method.

  New benchmarks should override CreateStorySet.
  """
  options = {}
  page_set = None
  test = timeline_based_measurement.TimelineBasedMeasurement
  SUPPORTED_PLATFORMS = [expectations_module.ALL]
  MAX_NUM_VALUES = sys.maxint

  def __init__(self, max_failures=None):
    """Creates a new Benchmark.

    Args:
      max_failures: The number of story run's failures before bailing
          from executing subsequent page runs. If None, we never bail.
    """
    self._expectations = typ_expectations.StoryExpectations(self.Name())
    self._max_failures = max_failures
    # TODO: There should be an assertion here that checks that only one of
    # the following is true:
    # * It's a TBM benchmark, with CreateCoreTimelineBasedMeasurementOptions
    #   defined.
    # * It's a legacy benchmark, with either CreatePageTest defined or
    #   Benchmark.test set.
    # See https://github.com/catapult-project/catapult/issues/3708

  def _CanRunOnPlatform(self, platform, finder_options):
    for p in self.SUPPORTED_PLATFORMS:
      # This is reusing StoryExpectation code, so it is a bit unintuitive. We
      # are trying to detect the opposite of the usual case in StoryExpectations
      # so we want to return True when ShouldDisable returns true, even though
      # we do not want to disable.
      if p.ShouldDisable(platform, finder_options):
        return True
    return False

  def Run(self, finder_options):
    """Do not override this method."""
    finder_options.target_platforms = self.GetSupportedPlatformNames(
        self.SUPPORTED_PLATFORMS)
    return story_runner.RunBenchmark(self, finder_options)

  @property
  def max_failures(self):
    return self._max_failures

  @classmethod
  def Name(cls):
    return '%s.%s' % (cls.__module__.split('.')[-1], cls.__name__)

  @classmethod
  def AddCommandLineArgs(cls, parser):
    group = optparse.OptionGroup(parser, '%s test options' % cls.Name())
    cls.AddBenchmarkCommandLineArgs(group)
    if group.option_list:
      parser.add_option_group(group)

  @classmethod
  def AddBenchmarkCommandLineArgs(cls, group):
    del group  # unused

  @classmethod
  def GetSupportedPlatformNames(cls, supported_platforms):
    """Returns a list of platforms supported by this benchmark.

    Returns:
      A set of names of supported platforms. The supported platforms are a list
      of strings that would match possible values from platform.GetOsName().
    """
    result = set()
    for p in supported_platforms:
      result.update(p.GetSupportedPlatformNames())
    return frozenset(result)

  @classmethod
  def SetArgumentDefaults(cls, parser):
    default_values = parser.get_default_values()
    invalid_options = [o for o in cls.options if not hasattr(default_values, o)]
    if invalid_options:
      raise InvalidOptionsError(
          'Invalid benchmark options: %s' % ', '.join(invalid_options))
    parser.set_defaults(**cls.options)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    pass

  # pylint: disable=unused-argument
  @classmethod
  def ShouldAddValue(cls, name, from_first_story_run):
    """Returns whether the named value should be added to PageTestResults.

    Override this method to customize the logic of adding values to test
    results.

    Args:
      name: The string name of a value being added.
      from_first_story_run: True if the named value was produced during the
          first run of the corresponding story.

    Returns:
      True if the value should be added to the test results, False otherwise.
    """
    return True

  def CustomizeOptions(self, finder_options):
    """Add options that are required by this benchmark."""

  def GetBugComponents(self):
    """Returns a GenericSet Diagnostic containing the benchmark's Monorail
       component.

    Returns:
      GenericSet Diagnostic with the benchmark's bug component name
    """
    benchmark_component = decorators.GetComponent(self)
    component_diagnostic_value = (
        [benchmark_component] if benchmark_component else [])
    return generic_set.GenericSet(component_diagnostic_value)

  def GetOwners(self):
    """Returns a Generic Diagnostic containing the benchmark's owners' emails
       in a list.

    Returns:
      Diagnostic with a list of the benchmark's owners' emails
    """
    return generic_set.GenericSet(decorators.GetEmails(self) or [])

  def GetDocumentationLink(self):
    """Returns a Generic Diagnostic containing the benchmark's documentation
       link in a string.

    Returns:
      Diagnostic with the link (string) to the benchmark documentation.
    """
    pair = ['Benchmark documentation link',
            decorators.GetDocumentationLink(self)]
    return generic_set.GenericSet([pair])

  def CreateCoreTimelineBasedMeasurementOptions(self):
    """Return the base TimelineBasedMeasurementOptions for this Benchmark.

    Additional chrome and atrace categories can be appended when running the
    benchmark with the --extra-chrome-categories and --extra-atrace-categories
    flags.

    Override this method to configure a TimelineBasedMeasurement benchmark. If
    this is not a TimelineBasedMeasurement benchmark, override CreatePageTest
    for PageTest tests. Do not override both methods.
    """
    return timeline_based_measurement.Options()

  def _GetTimelineBasedMeasurementOptions(self, options):
    """Return all timeline based measurements for the curren benchmark run.

    This includes the benchmark-configured measurements in
    CreateCoreTimelineBasedMeasurementOptions as well as the user-flag-
    configured options from --extra-chrome-categories and
    --extra-atrace-categories.
    """
    tbm_options = self.CreateCoreTimelineBasedMeasurementOptions()
    if options and options.extra_chrome_categories:
      # If Chrome tracing categories for this benchmark are not already
      # enabled, there is probably a good reason why. Don't change whether
      # Chrome tracing is enabled.
      assert tbm_options.config.enable_chrome_trace, (
          'This benchmark does not support Chrome tracing.')
      tbm_options.config.chrome_trace_config.category_filter.AddFilterString(
          options.extra_chrome_categories)
    if options and options.extra_atrace_categories:
      # Many benchmarks on Android run without atrace by default. Hopefully the
      # user understands that atrace is only supported on Android when setting
      # this option.
      tbm_options.config.enable_atrace_trace = True

      categories = tbm_options.config.atrace_config.categories
      if isinstance(categories, basestring):
        # Categories can either be a list or comma-separated string.
        # https://github.com/catapult-project/catapult/issues/3712
        categories = categories.split(',')
      for category in options.extra_atrace_categories.split(','):
        if category not in categories:
          categories.append(category)
      tbm_options.config.atrace_config.categories = categories
    if options and options.enable_systrace:
      tbm_options.config.chrome_trace_config.SetEnableSystrace()
    if options and options.experimental_proto_trace_format:
      tbm_options.config.chrome_trace_config.SetProtoTraceFormat()
    return tbm_options

  def CreatePageTest(self, options):  # pylint: disable=unused-argument
    """Return the PageTest for this Benchmark.

    Override this method for PageTest tests.
    Override, CreateCoreTimelineBasedMeasurementOptions to configure
    TimelineBasedMeasurement tests. Do not override both methods.

    Args:
      options: a browser_options.BrowserFinderOptions instance
    Returns:
      |test()| if |test| is a PageTest class.
      Otherwise, a TimelineBasedMeasurement instance.
    """
    is_page_test = issubclass(self.test, legacy_page_test.LegacyPageTest)
    is_story_test = issubclass(self.test, story_test.StoryTest)
    if not is_page_test and not is_story_test:
      raise TypeError('"%s" is not a PageTest or a StoryTest.' %
                      self.test.__name__)
    if is_page_test:
      # TODO: assert that CreateCoreTimelineBasedMeasurementOptions is not
      # defined. That's incorrect for a page test. See
      # https://github.com/catapult-project/catapult/issues/3708
      return self.test()  # pylint: disable=no-value-for-parameter

    opts = self._GetTimelineBasedMeasurementOptions(options)
    return self.test(opts)

  def CreateStorySet(self, options):
    """Creates the instance of StorySet used to run the benchmark.

    Can be overridden by subclasses.
    """
    del options  # unused
    # TODO(aiolos, nednguyen, eakufner): replace class attribute page_set with
    # story_set.
    if not self.page_set:
      raise NotImplementedError('This test has no "page_set" attribute.')
    return self.page_set()  # pylint: disable=not-callable

  def AugmentExpectationsWithFile(self, raw_data):
    self._expectations.GetBenchmarkExpectationsFromParser(raw_data)

  @property
  def expectations(self):
    return self._expectations
