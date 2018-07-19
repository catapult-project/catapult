# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.common import stored_object
from dashboard.common import descriptor
from dashboard.common import testing_common


class DescriptorTest(testing_common.TestCase):

  def setUp(self):
    super(DescriptorTest, self).setUp()
    stored_object.Set(descriptor.PARTIAL_TEST_SUITES_KEY, [
        'TEST_PARTIAL_TEST_SUITE',
    ])
    stored_object.Set(descriptor.COMPOSITE_TEST_SUITES_KEY, [
        'TEST_PARTIAL_TEST_SUITE:COMPOSITE',
        'TEST_PARTIAL_TEST_SUITE:two_two',
    ])
    stored_object.Set(descriptor.GROUPABLE_TEST_SUITE_PREFIXES_KEY, [
        'TEST_GROUPABLE%',
    ])
    stored_object.Set(descriptor.POLY_MEASUREMENT_TEST_SUITES_KEY, [
        'resource_sizes:foo',
        'sizes',
        'polymeasurement',
        'TEST_PARTIAL_TEST_SUITE:two_two',
    ])
    stored_object.Set(descriptor.TWO_TWO_TEST_SUITES_KEY, [
        'TEST_PARTIAL_TEST_SUITE:two_two',
    ])
    descriptor.Descriptor.ResetMemoizedConfigurationForTesting()

  def testFromTestPath_Empty(self):
    desc = descriptor.Descriptor.FromTestPathSync('')
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual(None, desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Short(self):
    desc = descriptor.Descriptor.FromTestPathSync('master')
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual(None, desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Bot(self):
    desc = descriptor.Descriptor.FromTestPathSync('master/bot')
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Suite(self):
    desc = descriptor.Descriptor.FromTestPathSync('master/bot/suite')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Measurement(self):
    desc = descriptor.Descriptor.FromTestPathSync('master/bot/suite/measure')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Statistic(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/suite/measure_avg')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Ref(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/suite/measure_avg/ref')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.REFERENCE_BUILD_TYPE, desc.build_type)

  def testFromTestPath_TestCase(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/suite/measure_avg/case')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('case', desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_All(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/suite/measure_avg/case_ref')
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('case', desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.REFERENCE_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Partial(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/TEST_PARTIAL_TEST_SUITE')
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_suite)

    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/TEST_PARTIAL_TEST_SUITE/COMPOSITE')
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('TEST_PARTIAL_TEST_SUITE:COMPOSITE', desc.test_suite)

  def testFromTestPath_Groupable(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/TEST_GROUPABLE%FOO')
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('TEST_GROUPABLE:FOO', desc.test_suite)

  def testFromTestPath_SystemHealth(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/system_health.common_desktop/measurement/'
        'browse_news/browse_news_cnn')
    self.assertEqual('browse:news:cnn', desc.test_case)

  def testFromTestPath_LongRunningTools(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/system_health.common_desktop/measurement/'
        'long_running_tools/long_running_tools:gmail')
    self.assertEqual('long_running_tools:gmail', desc.test_case)

  def testFromTestPath_ResourceSizes(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/resource_sizes:foo/a/b/c/d')
    self.assertEqual('a:b:c:d', desc.measurement)
    self.assertEqual(None, desc.test_case)

  def testFromTestPath_NoMitigations(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/polymeasurement/a/b/c/' +
        descriptor.NO_MITIGATIONS_CASE)
    self.assertEqual('a:b:c', desc.measurement)
    self.assertEqual(descriptor.NO_MITIGATIONS_CASE, desc.test_case)

  def testFromTestPath_Unparsed(self):
    with self.assertRaises(ValueError):
      descriptor.Descriptor.FromTestPathSync(
          'master/bot/suite/measurement/case/extra')
    with self.assertRaises(ValueError):
      descriptor.Descriptor.FromTestPathSync(
          'master/bot/suite/measurement/case/extra/ref')

  def testFromTestPath_Memory(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/memory.top_10_mobile/measurement/ground')
    self.assertEqual('measurement', desc.measurement)
    self.assertEqual(None, desc.test_case)

    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/memory.top_10_mobile/measurement/ground/page')
    self.assertEqual('measurement', desc.measurement)
    self.assertEqual('ground:page', desc.test_case)

  def testFromTestPath_Sizes(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/sizes/a/b/c/d/e/f/g/h/i')
    self.assertEqual('sizes', desc.test_suite)
    self.assertEqual('a:b:c:d:e:f', desc.measurement)
    self.assertEqual('g:h:i', desc.test_case)

  def testFromTestPath_TwoTwo(self):
    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/TEST_PARTIAL_TEST_SUITE/two_two/a/b/c/d')
    self.assertEqual('TEST_PARTIAL_TEST_SUITE:two_two', desc.test_suite)
    self.assertEqual('a:b', desc.measurement)
    self.assertEqual('c:d', desc.test_case)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

    desc = descriptor.Descriptor.FromTestPathSync(
        'master/bot/TEST_PARTIAL_TEST_SUITE/two_two/a/b/c/d/ref')
    self.assertEqual('TEST_PARTIAL_TEST_SUITE:two_two', desc.test_suite)
    self.assertEqual('a:b', desc.measurement)
    self.assertEqual('c:d', desc.test_case)
    self.assertEqual(descriptor.REFERENCE_BUILD_TYPE, desc.build_type)

  def testToTestPaths_Empty(self):
    self.assertEqual([], descriptor.Descriptor().ToTestPathsSync())

  def testToTestPaths_Bot(self):
    self.assertEqual(['master/bot'], descriptor.Descriptor(
        bot='master:bot').ToTestPathsSync())

  def testToTestPaths_Suite(self):
    self.assertEqual(['master/bot/suite'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite').ToTestPathsSync())

  def testToTestPaths_Measurement(self):
    self.assertEqual(['master/bot/suite/measure'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure').ToTestPathsSync())

  def testToTestPaths_Statistic(self):
    self.assertEqual(['master/bot/suite/measure_avg'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        statistic='avg').ToTestPathsSync())

  def testToTestPaths_Ref(self):
    test_path = 'master/bot/suite/measure'
    expected = [test_path + '_ref', test_path + '/ref']
    self.assertEqual(expected, descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        build_type=descriptor.REFERENCE_BUILD_TYPE).ToTestPathsSync())

  def testToTestPaths_TestCase(self):
    self.assertEqual(['master/bot/suite/measure/case'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        test_case='case').ToTestPathsSync())

  def testToTestPaths_All(self):
    test_path = 'master/bot/suite/measure_avg/case'
    expected = [test_path + '_ref', test_path + '/ref']
    self.assertEqual(expected, descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        test_case='case',
        statistic='avg',
        build_type=descriptor.REFERENCE_BUILD_TYPE).ToTestPathsSync())

  def testToTestPaths_Composite(self):
    expected = 'master/bot/TEST_PARTIAL_TEST_SUITE/COMPOSITE'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='TEST_PARTIAL_TEST_SUITE:COMPOSITE').ToTestPathsSync())

  def testToTestPaths_Groupable(self):
    self.assertEqual(['master/bot/TEST_GROUPABLE%FOO'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='TEST_GROUPABLE:FOO').ToTestPathsSync())

  def testToTestPath_SystemHealth(self):
    expected = ('master/bot/system_health.common_desktop/measurement/'
                'browse_news/browse_news_cnn')
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='system_health.common_desktop',
        measurement='measurement',
        test_case='browse:news:cnn').ToTestPathsSync())

  def testToTestPath_LongRunningTools(self):
    expected = ('master/bot/system_health.common_desktop/measurement/'
                'long_running_tools/long_running_tools_gmail')
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='system_health.common_desktop',
        measurement='measurement',
        test_case='long_running_tools:gmail').ToTestPathsSync())

  def testToTestPath_ResourceSizes(self):
    expected = 'master/bot/resource sizes (foo)/a/b/c'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='resource_sizes:foo',
        measurement='a:b:c').ToTestPathsSync())

  def testToTestPath_Memory(self):
    expected = 'master/bot/memory.top_10_mobile/measure/ground/page'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='memory.top_10_mobile',
        measurement='measure',
        test_case='ground:page').ToTestPathsSync())

  def testToTestPath_Sizes(self):
    expected = 'master/bot/sizes/a/b/c/d/e/f/g/h/i'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='sizes',
        measurement='a:b:c:d:e:f',
        test_case='g:h:i').ToTestPathsSync())

  def testToTestPath_TwoTwo(self):
    expected = 'master/bot/TEST_PARTIAL_TEST_SUITE/two_two/a/b/c/d'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='TEST_PARTIAL_TEST_SUITE:two_two',
        measurement='a:b',
        test_case='c:d').ToTestPathsSync())

if __name__ == '__main__':
  unittest.main()
