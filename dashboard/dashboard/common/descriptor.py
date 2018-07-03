# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Translate between test paths and Descriptors.

Test paths describe a timeseries by its path in a tree of timeseries.
Descriptors describe a timeseries semantically by its characteristics.
Descriptors allow users to navigate timeseries use meaningful words like
"measurement" and "test case" instead of meaningless words like "subtest".
Test paths can be arbitrarily long, but there are a fixed number of semantic
characteristics. Multiple test path components may be joined into a single
characteristic.

These are timeseries Descriptors, not test suite descriptors, not line
descriptors, not fetch descriptors.

This translation layer should be temporary until the descriptor concept can be
pushed down into the Model layer.
"""

from dashboard.common import stored_object

TEST_BUILD_TYPE = 'test'
REFERENCE_BUILD_TYPE = 'ref'
STATISTICS = ['avg', 'count', 'max', 'min', 'std', 'sum']
PARTIAL_TEST_SUITES_KEY = 'partial_test_suites'
COMPOSITE_TEST_SUITES_KEY = 'composite_test_suites'
GROUPABLE_TEST_SUITE_PREFIXES_KEY = 'groupable_test_suite_prefixes'


class Descriptor(object):
  """Describe a timeseries by its characteristics.

  Supports partial test paths (e.g. test suite paths) by allowing some
  characteristics to be None.
  """

  def __init__(self, test_suite=None, measurement=None, bot=None,
               test_case=None, statistic=None, build_type=None):
    self.test_suite = test_suite
    self.measurement = measurement
    self.bot = bot
    self.test_case = test_case
    self.statistic = statistic
    self.build_type = build_type

  def __repr__(self):
    return 'Descriptor(%r, %r, %r, %r, %r, %r)' % (
        self.test_suite, self.measurement, self.bot, self.test_case,
        self.statistic, self.build_type)

  @classmethod
  def ResetMemoizedConfigurationForTesting(cls):
    cls.PARTIAL_TEST_SUITES = None
    cls.COMPOSITE_TEST_SUITES = None
    cls.GROUPABLE_TEST_SUITE_PREFIXES = None

  PARTIAL_TEST_SUITES = None

  @classmethod
  def _PartialTestSuites(cls):
    """Returns a list of test path component strings that must be joined with
    the subsequent test path component in order to form a composite test suite.
    Some are internal-only, but there's no need to store a separate list for
    external users.
    """
    if cls.PARTIAL_TEST_SUITES is None:
      cls.PARTIAL_TEST_SUITES = stored_object.Get(PARTIAL_TEST_SUITES_KEY) or ()
    return cls.PARTIAL_TEST_SUITES

  COMPOSITE_TEST_SUITES = None

  @classmethod
  def _CompositeTestSuites(cls):
    """
    Returns a list of test suites composed of 2 or more test path components.
    All composite test suites start with a partial test suite, but not all test
    suites that start with a partial test suite are composite.
    Some are internal-only, but there's no need to store a separate list for
    external users.
    """
    if cls.COMPOSITE_TEST_SUITES is None:
      cls.COMPOSITE_TEST_SUITES = stored_object.Get(
          COMPOSITE_TEST_SUITES_KEY) or ()
    return cls.COMPOSITE_TEST_SUITES

  GROUPABLE_TEST_SUITE_PREFIXES = None

  @classmethod
  def _GroupableTestSuitePrefixes(cls):
    """
    Returns a list of prefixes of test suites that are transformed to allow the
    UI to group them.
    Some are internal-only, but there's no need to store a separate list for
    external users.
    """
    if cls.GROUPABLE_TEST_SUITE_PREFIXES is None:
      cls.GROUPABLE_TEST_SUITE_PREFIXES = stored_object.Get(
          GROUPABLE_TEST_SUITE_PREFIXES_KEY) or ()
    return cls.GROUPABLE_TEST_SUITE_PREFIXES

  @classmethod
  def FromTestPath(cls, path):
    """Parse a test path into a Descriptor.

    Args:
      path: Array of strings of any length.

    Returns:
      Descriptor
    """
    if len(path) < 2:
      return cls()

    bot = path.pop(0) + ':' + path.pop(0)
    if len(path) == 0:
      return cls(bot=bot)

    test_suite = path.pop(0)

    if test_suite in cls._PartialTestSuites():
      if len(path) == 0:
        return cls(bot=bot)
      test_suite += ':' + path.pop(0)

    if test_suite.startswith('resource_sizes '):
      test_suite = 'resource_sizes:' + test_suite[16:-1]
    else:
      for prefix in cls._GroupableTestSuitePrefixes():
        if test_suite.startswith(prefix):
          test_suite = prefix[:-1] + ':' + test_suite[len(prefix):]
          break

    if len(path) == 0:
      return cls(test_suite=test_suite, bot=bot)

    build_type = TEST_BUILD_TYPE
    measurement = path.pop(0)
    statistic = None
    # TODO(crbug.com/853258) some measurements include path[4]
    for suffix in STATISTICS:
      if measurement.endswith('_' + suffix):
        statistic = suffix
        measurement = measurement[:-(1 + len(suffix))]
    if len(path) == 0:
      return cls(test_suite=test_suite, bot=bot, measurement=measurement,
                 build_type=build_type, statistic=statistic)

    test_case = path.pop(0)
    if test_case.endswith('_ref'):
      test_case = test_case[:-4]
      build_type = REFERENCE_BUILD_TYPE
    if test_case == REFERENCE_BUILD_TYPE:
      build_type = REFERENCE_BUILD_TYPE
      test_case = None
    # TODO(crbug.com/853258) some test_cases include path[5] and/or path[6]
    # and/or path[7]
    # TODO(crbug.com/853258) some test_cases need to be modified

    return cls(test_suite=test_suite, bot=bot, measurement=measurement,
               statistic=statistic, test_case=test_case, build_type=build_type)

  def ToTestPaths(self):
    # There may be multiple possible test paths for a given Descriptor.

    if not self.bot:
      return []

    test_path = self.bot.replace(':', '/')
    if not self.test_suite:
      return [test_path]

    test_path += '/'

    if self.test_suite.startswith('resource_sizes:'):
      test_path += 'resource sizes (%s)' % self.test_suite[15:]
    elif self.test_suite in self._CompositeTestSuites():
      test_path += self.test_suite.replace(':', '/')
    else:
      first_part = self.test_suite.split(':')[0]
      for prefix in self._GroupableTestSuitePrefixes():
        if prefix[:-1] == first_part:
          test_path += prefix + self.test_suite[len(first_part) + 1:]
          break
      else:
        test_path += self.test_suite
    if not self.measurement:
      return [test_path]

    # TODO(crbug.com/853258) some measurements need to be modified
    test_path += '/' + self.measurement
    if self.statistic:
      test_path += '_' + self.statistic
    if self.test_case:
      # TODO(crbug.com/853258) some test_cases need to be modified
      test_path += '/' + self.test_case

    candidates = [test_path]
    if self.build_type == REFERENCE_BUILD_TYPE:
      candidates = [candidate + suffix
                    for candidate in candidates
                    for suffix in ['_ref', '/ref']]
    return candidates
