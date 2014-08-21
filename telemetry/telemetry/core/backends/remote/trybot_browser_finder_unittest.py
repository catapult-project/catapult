# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import StringIO
import unittest

from telemetry.core import browser_options
from telemetry.core.backends.remote import trybot_browser_finder
from telemetry.unittest import simple_mock
from telemetry.unittest import system_stub


class TrybotBrowserFinderTest(unittest.TestCase):

  def setUp(self):
    self.log_output = StringIO.StringIO()
    self.stream_handler = logging.StreamHandler(self.log_output)
    logging.getLogger().addHandler(self.stream_handler)
    self._real_subprocess = trybot_browser_finder.subprocess
    self._real_urllib2 = trybot_browser_finder.urllib2
    self._stubs = system_stub.Override(trybot_browser_finder, ['sys', 'open'])

  def tearDown(self):
    logging.getLogger().removeHandler(self.stream_handler)
    self.log_output.close()
    trybot_browser_finder.subprocess = self._real_subprocess
    trybot_browser_finder.urllib2 = self._real_urllib2
    self._stubs.Restore()

  def _ExpectProcesses(self, args):
    mock_subprocess = simple_mock.MockObject()
    mock_subprocess.SetAttribute('PIPE', simple_mock.MockObject())
    for arg in args:
      mock_popen = simple_mock.MockObject()
      mock_popen.ExpectCall('communicate').WillReturn(arg[1][1:])
      mock_popen.ExpectCall('poll').WillReturn(arg[1][0])
      mock_subprocess.ExpectCall(
          'Popen').WithArgs(arg[0]).WillReturn(mock_popen)
    trybot_browser_finder.subprocess = mock_subprocess

  def test_find_all_browser_types_list(self):
    finder_options = browser_options.BrowserFinderOptions(browser_type='list')
    trybot_browser_finder.urllib2 = simple_mock.MockObject()
    trybot_browser_finder.urllib2.ExpectCall('urlopen').WithArgs(
        'http://build.chromium.org/p/tryserver.chromium.perf/json').WillReturn(
            StringIO.StringIO(json.dumps({'builders': {
                'android_nexus4_perf_bisect': 'stuff',
                'mac_10_9_perf_bisect': 'otherstuff',
                'win_perf_bisect_builder': 'not a trybot',
            }})))
    self.assertEquals(
        ['trybot-android-nexus4', 'trybot-mac-10-9'],
        # pylint: disable=W0212
        sorted(trybot_browser_finder.FindAllBrowserTypes(finder_options)))

  def test_find_all_browser_types_trybot(self):
    finder_options = browser_options.BrowserFinderOptions(
        browser_type='trybot-win')
    trybot_browser_finder.urllib2 = simple_mock.MockObject()
    trybot_browser_finder.urllib2.ExpectCall('urlopen').WithArgs(
        'http://build.chromium.org/p/tryserver.chromium.perf/json').WillReturn(
            StringIO.StringIO(json.dumps({'builders': {
                'android_nexus4_perf_bisect': 'stuff',
                'mac_10_9_perf_bisect': 'otherstuff',
                'win_perf_bisect_builder': 'not a trybot',
            }})))
    self.assertEquals(
        ['trybot-android-nexus4', 'trybot-mac-10-9'],
        # pylint: disable=W0212
        sorted(trybot_browser_finder.FindAllBrowserTypes(finder_options)))

  def test_find_all_browser_types_non_trybot_browser(self):
    finder_options = browser_options.BrowserFinderOptions(
        browser_type='release')
    trybot_browser_finder.urllib2 = simple_mock.MockObject()
    self.assertEquals(
        [],
        # pylint: disable=W0212
        sorted(trybot_browser_finder.FindAllBrowserTypes(finder_options)))

  def test_constructor(self):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    # pylint: disable=W0212
    self.assertEquals('android', browser._target_os)
    # pylint: disable=W0212
    self.assertEquals('android_nexus4_perf_bisect', browser._buildername)

  def test_no_git(self):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (128, None, None)),
    ))
    browser.RunRemote()
    self.assertEquals(
        'Must be in a git repository to send changes to trybots.\n',
        self.log_output.getvalue())

  def test_dirty_tree(self):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, 'dirty tree', None)),
    ))

    browser.RunRemote()
    self.assertEquals(
        'Cannot send a try job with a dirty tree. Commit locally first.\n',
        self.log_output.getvalue())

  def test_no_local_commits(self):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, '', None)),
    ))

    browser.RunRemote()
    self.assertEquals(
        ('No local changes on branch br. browser=trybot-android-nexus4 '
         'argument sends local changes to the android_nexus4_perf_bisect '
         'perf trybot.\n'),
        self.log_output.getvalue())

  def test_branch_checkout_fails(self):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, 'logs here', None)),
        (['git', 'checkout', '-b', 'telemetry-tryjob'],
         (1, None, 'fatal: A branch named \'telemetry-try\' already exists.')),
    ))

    browser.RunRemote()
    self.assertEquals(
        ('Error creating branch telemetry-tryjob. '
         'Please delete it if it exists.\n'
         'fatal: A branch named \'telemetry-try\' already exists.\n'),
        self.log_output.getvalue())

  def _GetConfigForBrowser(self, name, branch):
    finder_options = browser_options.BrowserFinderOptions()
    browser = trybot_browser_finder.PossibleTrybotBrowser(name, finder_options)
    bot = '%s_perf_bisect' % name.replace('trybot-', '').replace('-', '_')
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, branch, None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, 'logs here', None)),
        (['git', 'checkout', '-b', 'telemetry-tryjob'], (0, None, None)),
        (['git', 'commit', '-a', '-m', 'bisect config'], (0, None, None)),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob'],
         (0, 'stuff https://codereview.chromium.org/12345 stuff', None)),
        (['git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b', bot],
         (0, None, None)),
        (['git', 'checkout', branch], (0, None, None)),
        (['git', 'branch', '-D', 'telemetry-tryjob'], (0, None, None))
    ))
    self._stubs.sys.argv = [
        'tools/perf/run_benchmark',
        '--browser=%s' % browser,
        'sunspider']
    cfg = StringIO.StringIO()
    self._stubs.open.files = {'tools/run-perf-test.cfg': cfg}

    browser.RunRemote()
    return cfg.getvalue()

  def test_config_android(self):
    config = self._GetConfigForBrowser('trybot-android-nexus4', 'somebranch')
    self.assertEquals(
        ('config = {\n'
         '  "command": "./tools/perf/run_measurement '
         '--browser=android-chrome-shell sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

  def test_config_mac(self):
    config = self._GetConfigForBrowser('trybot-mac-10-9', 'currentwork')
    self.assertEquals(
        ('config = {\n'
         '  "command": "./tools/perf/run_measurement '
         '--browser=release sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

