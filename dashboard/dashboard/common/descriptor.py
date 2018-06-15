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

This translation layer should be temporary until the descriptor concept can be
pushed down into the Model layer.
"""


TEST_BUILD_TYPE = 'test'
REFERENCE_BUILD_TYPE = 'ref'
STATISTICS = ['avg', 'count', 'max', 'min', 'std', 'sum']


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
  def FromTestPath(cls, path):
    """Parse a test path into a Descriptor.

    Args:
      path: Array of strings of any length.

    Returns:
      Descriptor
    """
    if len(path) < 2:
      return cls()

    bot = path[0] + ':' + path[1]
    if len(path) == 2:
      return cls(bot=bot)

    test_suite = path[2]
    # TODO(crbug.com/853258) some test_suites include path[3]
    if len(path) == 3:
      return cls(test_suite=test_suite, bot=bot)

    build_type = TEST_BUILD_TYPE
    measurement = path[3]
    statistic = None
    # TODO(crbug.com/853258) some measurements include path[4]
    for suffix in STATISTICS:
      if measurement.endswith('_' + suffix):
        statistic = suffix
        measurement = measurement[:-(1 + len(suffix))]
    if len(path) == 4:
      return cls(test_suite=test_suite, bot=bot, measurement=measurement,
                 build_type=build_type, statistic=statistic)

    test_case = path[4]
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

    # TODO(crbug.com/853258) some test_suites need to be modified
    test_path += '/' + self.test_suite
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
