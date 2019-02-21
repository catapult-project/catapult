# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest
import json


from telemetry import project_config
from telemetry import decorators
from telemetry.core import util
from telemetry.testing import run_tests
from telemetry.testing import unittest_runner

class MockArgs(object):
  def __init__(self):
    self.positional_args = []
    self.test_filter = ''
    self.exact_test_filter = True
    self.run_disabled_tests = False
    self.skip = []


class MockPossibleBrowser(object):
  def __init__(self, browser_type, os_name, os_version_name,
               supports_tab_control):
    self.browser_type = browser_type
    self.platform = MockPlatform(os_name, os_version_name)
    self.supports_tab_control = supports_tab_control


class MockPlatform(object):
  def __init__(self, os_name, os_version_name):
    self.os_name = os_name
    self.os_version_name = os_version_name

  def GetOSName(self):
    return self.os_name

  def GetOSVersionName(self):
    return self.os_version_name

  def GetOSVersionDetailString(self):
    return ''


class RunTestsUnitTest(unittest.TestCase):
  def setUp(self):
    self._test_result = {}

  def _ExtractTestResults(self, test_result):
    delimiter = test_result['path_delimiter']
    failures = []
    successes = []
    skips = []
    def _IsLeafNode(node):
      test_dict = node[1]
      return ('expected' in test_dict and
              isinstance(test_dict['expected'], basestring))
    node_queues = []
    for t in test_result['tests']:
      node_queues.append((t, test_result['tests'][t]))
    while node_queues:
      node = node_queues.pop()
      full_test_name, test_dict = node
      if _IsLeafNode(node):
        if all(res not in test_dict['expected'].split() for res in
               test_dict['actual'].split()):
          failures.append(full_test_name)
        elif test_dict['actual'] == 'SKIP':
          skips.append(full_test_name)
        else:
          successes.append(full_test_name)
      else:
        for k in test_dict:
          node_queues.append(
              ('%s%s%s' % (full_test_name, delimiter, k),
               test_dict[k]))
    return successes, failures, skips

  def baseTest(self,
               failures, successes, skips, test_name='',
               extra_args=None):
    extra_args = extra_args or []
    config = project_config.ProjectConfig(
        top_level_dir=os.path.join(util.GetTelemetryDir(), 'examples'),
        client_configs=[],
        benchmark_dirs=[
            os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests')]
    )
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.close()
    temp_file_name = temp_file.name
    try:
      passed_args = [test_name, '--no-browser', ('--write-full-results-to=%s' %
                                                 temp_file_name)]
      ret = unittest_runner.Run(config, passed_args=passed_args + extra_args)
      self.assertEquals(ret, 0)
      with open(temp_file_name) as f:
        self._test_result = json.load(f)
      (actual_successes,
       actual_failures,
       actual_skips) = self._ExtractTestResults(self._test_result)
      self.assertEquals(set(actual_failures), set(failures))
      self.assertEquals(set(actual_successes), set(successes))
      self.assertEquals(set(actual_skips), set(skips))
    finally:
      os.remove(temp_file_name)

  def _RunUnitWithExpectationFile(self, full_test_name, expectation,
                                  test_tags='foo', extra_args=None,
                                  expected_exit_code=0):
    extra_args = extra_args or []
    expectations = ('# tags: [ foo bar mac ]\n'
                    'crbug.com/123 [ %s ] %s [ %s ]')
    expectations = expectations % (test_tags, full_test_name, expectation)
    expectations_file = tempfile.NamedTemporaryFile(delete=False)
    expectations_file.write(expectations)
    results = tempfile.NamedTemporaryFile(delete=False)
    results.close()
    expectations_file.close()
    config = project_config.ProjectConfig(
        top_level_dir=os.path.join(util.GetTelemetryDir(), 'examples'),
        client_configs=[],
        expectations_files=[expectations_file.name],
        benchmark_dirs=[
            os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests')]
    )
    try:
      passed_args = ([full_test_name, '--no-browser',
                      ('--write-full-results-to=%s' % results.name)] +
                     ['--tag=%s' % tag for tag in test_tags.split()])
      ret = unittest_runner.Run(config, passed_args=passed_args + extra_args)
      self.assertEqual(ret, expected_exit_code)
      with open(results.name) as f:
        self._test_result = json.load(f)
    finally:
      os.remove(expectations_file.name)
      os.remove(results.name)
    return self._test_result

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testTestFailsAllRetryOnFailureRetriesAndIsNotaRegression(self):
    self._RunUnitWithExpectationFile(('unit_tests_test.FailingTest.test_fail'),
                                     'RetryOnFailure Failure',
                                     extra_args=['--retry-limit=3',
                                                 ('--retry-only-retry'
                                                  '-on-failure-tests')],
                                     expected_exit_code=0)
    results = (self._test_result['tests']['unit_tests_test']
               ['FailingTest']['test_fail'])
    self.assertEqual(results['actual'], 'FAIL FAIL FAIL FAIL')
    self.assertEqual(results['expected'], 'FAIL')
    self.assertNotIn('is_unexpected', results)
    self.assertNotIn('is_regression', results)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testDoNotRetryExpectedFailure(self):
    self._RunUnitWithExpectationFile('unit_tests_test.FailingTest.test_fail',
                                     'Failure', extra_args=['--retry-limit=3'])
    test_result = (self._test_result['tests']['unit_tests_test']['FailingTest']
                   ['test_fail'])
    self.assertEqual(test_result['actual'], 'FAIL')
    self.assertEqual(test_result['expected'], 'FAIL')
    self.assertNotIn('is_unexpected', test_result)
    self.assertNotIn('is_regression', test_result)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testRetryOnFailureExpectationWithPassingTest(self):
    self._RunUnitWithExpectationFile('unit_tests_test.PassingTest.test_pass',
                                     'RetryOnFailure')
    test_result = (self._test_result['tests']['unit_tests_test']['PassingTest']
                   ['test_pass'])
    self.assertEqual(test_result['actual'], 'PASS')
    self.assertEqual(test_result['expected'], 'PASS')
    self.assertNotIn('is_unexpected', test_result)
    self.assertNotIn('is_regression', test_result)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testSkipTestCmdArgNoExpectationsFile(self):
    self.baseTest([],
                  [],
                  ['unit_tests_test.PassingTest.test_pass'],
                  test_name='unit_tests_test.PassingTest.test_pass',
                  extra_args=['--skip=*test_pass'])
    test_result = (self._test_result['tests']['unit_tests_test']
                   ['PassingTest']['test_pass'])
    self.assertEqual(test_result['expected'], 'SKIP')
    self.assertEqual(test_result['actual'], 'SKIP')
    self.assertNotIn('is_unexpected', test_result)
    self.assertNotIn('is_regression', test_result)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testSkipTestNoExpectationsFile(self):
    self.baseTest(
        [],
        [],
        ['unit_tests_test.SkipTest.test_skip'],
        test_name='unit_tests_test.SkipTest.test_skip')
    result = (self._test_result['tests']['unit_tests_test']
              ['SkipTest']['test_skip'])
    self.assertEqual(result['actual'], 'SKIP')
    self.assertEqual(result['expected'], 'SKIP')
    self.assertNotIn('is_unexpected', result)
    self.assertNotIn('is_regression', result)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testSkipTestWithExpectationsFileWithSkipExpectation(self):
    self._RunUnitWithExpectationFile('unit_tests_test.PassingTest.test_pass',
                                     'Skip Failure Crash')
    test_result = (self._test_result['tests']['unit_tests_test']['PassingTest']
                   ['test_pass'])
    self.assertEqual(test_result['actual'], 'SKIP')
    self.assertEqual(test_result['expected'], 'CRASH FAIL SKIP')
    self.assertNotIn('is_unexpected', test_result)
    self.assertNotIn('is_regression', test_result)

  @decorators.Disabled('chromeos')  # crbug.com/696553
  def testSkipTestCmdArgsWithExpectationsFile(self):
    self._RunUnitWithExpectationFile('unit_tests_test.PassingTest.test_pass',
                                     'Crash Failure',
                                     extra_args=['--skip=*test_pass'])
    test_result = (self._test_result['tests']['unit_tests_test']['PassingTest']
                   ['test_pass'])
    self.assertEqual(test_result['actual'], 'SKIP')
    self.assertEqual(test_result['expected'], 'SKIP')
    self.assertNotIn('is_unexpected', test_result)
    self.assertNotIn('is_regression', test_result)

  def _GetEnabledTests(self, browser_type, os_name, os_version_name,
                       supports_tab_control, args=None):
    if not args:
      args = MockArgs()
    runner = run_tests.typ.Runner()
    host = runner.host
    runner.top_level_dirs = [util.GetTelemetryDir()]
    runner.args.tests = [
        host.join(util.GetTelemetryDir(), 'telemetry', 'testing',
                  'disabled_cases.py')
    ]
    possible_browser = MockPossibleBrowser(
        browser_type, os_name, os_version_name, supports_tab_control)
    runner.classifier = run_tests.GetClassifier(args, possible_browser)
    _, test_set = runner.find_tests(runner.args)
    return set(test.name.split('.')[-1] for test in test_set.parallel_tests)

  def testSystemMacMavericks(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testMacOnly',
             'testMavericksOnly',
             'testNoChromeOS',
             'testNoWinLinux',
             'testSystemOnly',
             'testHasTabs']),
        self._GetEnabledTests('system', 'mac', 'mavericks', True))

  def testSystemMacLion(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testMacOnly',
             'testNoChromeOS',
             'testNoMavericks',
             'testNoWinLinux',
             'testSystemOnly',
             'testHasTabs']),
        self._GetEnabledTests('system', 'mac', 'lion', True))

  def testCrosGuestChromeOS(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testChromeOSOnly',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testNoWinLinux',
             'testHasTabs']),
        self._GetEnabledTests('cros-guest', 'chromeos', '', True))

  def testCanaryWindowsWin7(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testNoChromeOS',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testWinOrLinuxOnly',
             'testHasTabs']),
        self._GetEnabledTests('canary', 'win', 'win7', True))

  def testDoesntHaveTabs(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testNoChromeOS',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testWinOrLinuxOnly']),
        self._GetEnabledTests('canary', 'win', 'win7', False))

  def testSkip(self):
    args = MockArgs()
    args.skip = ['telemetry.*testNoMac', '*NoMavericks',
                 'telemetry.testing.disabled_cases.DisabledCases.testNoSystem']
    self.assertEquals(
        set(['testAllEnabled',
             'testAllEnabledVersion2',
             'testNoChromeOS',
             'testWinOrLinuxOnly',
             'testHasTabs']),
        self._GetEnabledTests('canary', 'win', 'win7', True, args))

  def testtPostionalArgsTestFiltering(self):
    args = MockArgs()
    args.positional_args = ['testAllEnabled']
    args.exact_test_filter = False
    self.assertEquals(
        set(['testAllEnabled', 'testAllEnabledVersion2']),
        self._GetEnabledTests('system', 'win', 'win7', True, args))

  def testPostionalArgsTestFiltering(self):
    args = MockArgs()
    args.test_filter = (
        'telemetry.testing.disabled_cases.DisabledCases.testAllEnabled::'
        'telemetry.testing.disabled_cases.DisabledCases.testNoMavericks::'
        'testAllEnabledVersion2')  # Partial test name won't match
    args.exact_test_filter = False
    self.assertEquals(
        set(['testAllEnabled', 'testNoMavericks']),
        self._GetEnabledTests('system', 'win', 'win7', True, args))
