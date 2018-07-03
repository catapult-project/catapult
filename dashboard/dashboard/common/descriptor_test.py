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
    ])
    stored_object.Set(descriptor.GROUPABLE_TEST_SUITE_PREFIXES_KEY, [
        'TEST_GROUPABLE%',
    ])
    descriptor.Descriptor.ResetMemoizedConfigurationForTesting()

  def testFromTestPath_Empty(self):
    desc = descriptor.Descriptor.FromTestPath([])
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual(None, desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Short(self):
    desc = descriptor.Descriptor.FromTestPath([''])
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual(None, desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Bot(self):
    desc = descriptor.Descriptor.FromTestPath(['master', 'bot'])
    self.assertEqual(None, desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Suite(self):
    desc = descriptor.Descriptor.FromTestPath(['master', 'bot', 'suite'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual(None, desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(None, desc.build_type)

  def testFromTestPath_Measurement(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'suite', 'measure'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual(None, desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Statistic(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'suite', 'measure_avg'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Ref(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'suite', 'measure_avg', 'ref'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.REFERENCE_BUILD_TYPE, desc.build_type)

  def testFromTestPath_TestCase(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'suite', 'measure_avg', 'case'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('case', desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.TEST_BUILD_TYPE, desc.build_type)

  def testFromTestPath_All(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'suite', 'measure_avg', 'case_ref'])
    self.assertEqual('suite', desc.test_suite)
    self.assertEqual('measure', desc.measurement)
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('case', desc.test_case)
    self.assertEqual('avg', desc.statistic)
    self.assertEqual(descriptor.REFERENCE_BUILD_TYPE, desc.build_type)

  def testFromTestPath_Partial(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'TEST_PARTIAL_TEST_SUITE'])
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual(None, desc.test_suite)

    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'TEST_PARTIAL_TEST_SUITE', 'COMPOSITE'])
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('TEST_PARTIAL_TEST_SUITE:COMPOSITE', desc.test_suite)

  def testFromTestPath_Groupable(self):
    desc = descriptor.Descriptor.FromTestPath([
        'master', 'bot', 'TEST_GROUPABLE%FOO'])
    self.assertEqual('master:bot', desc.bot)
    self.assertEqual('TEST_GROUPABLE:FOO', desc.test_suite)

  def testToTestPaths_Empty(self):
    self.assertEqual([], descriptor.Descriptor().ToTestPaths())

  def testToTestPaths_Bot(self):
    self.assertEqual(['master/bot'], descriptor.Descriptor(
        bot='master:bot').ToTestPaths())

  def testToTestPaths_Suite(self):
    self.assertEqual(['master/bot/suite'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite').ToTestPaths())

  def testToTestPaths_Measurement(self):
    self.assertEqual(['master/bot/suite/measure'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure').ToTestPaths())

  def testToTestPaths_Statistic(self):
    self.assertEqual(['master/bot/suite/measure_avg'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        statistic='avg').ToTestPaths())

  def testToTestPaths_Ref(self):
    test_path = 'master/bot/suite/measure'
    expected = [test_path + '_ref', test_path + '/ref']
    self.assertEqual(expected, descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        build_type=descriptor.REFERENCE_BUILD_TYPE).ToTestPaths())

  def testToTestPaths_TestCase(self):
    self.assertEqual(['master/bot/suite/measure/case'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        test_case='case').ToTestPaths())

  def testToTestPaths_All(self):
    test_path = 'master/bot/suite/measure_avg/case'
    expected = [test_path + '_ref', test_path + '/ref']
    self.assertEqual(expected, descriptor.Descriptor(
        bot='master:bot',
        test_suite='suite',
        measurement='measure',
        test_case='case',
        statistic='avg',
        build_type=descriptor.REFERENCE_BUILD_TYPE).ToTestPaths())

  def testToTestPaths_Composite(self):
    expected = 'master/bot/TEST_PARTIAL_TEST_SUITE/COMPOSITE'
    self.assertEqual([expected], descriptor.Descriptor(
        bot='master:bot',
        test_suite='TEST_PARTIAL_TEST_SUITE:COMPOSITE').ToTestPaths())

  def testToTestPaths_Groupable(self):
    self.assertEqual(['master/bot/TEST_GROUPABLE%FOO'], descriptor.Descriptor(
        bot='master:bot',
        test_suite='TEST_GROUPABLE:FOO').ToTestPaths())


if __name__ == '__main__':
  unittest.main()
