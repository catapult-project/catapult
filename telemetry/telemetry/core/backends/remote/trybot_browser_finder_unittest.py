# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import StringIO
import unittest

from telemetry.core.backends.remote import trybot_browser_finder
from telemetry.core import browser_options
from telemetry.unittest_util import simple_mock
from telemetry.unittest_util import system_stub


class TrybotBrowserFinderTest(unittest.TestCase):

  def setUp(self):
    self.log_output = StringIO.StringIO()
    self.stream_handler = logging.StreamHandler(self.log_output)
    logging.getLogger().addHandler(self.stream_handler)
    self._real_subprocess = trybot_browser_finder.subprocess
    self._real_urllib2 = trybot_browser_finder.urllib2
    self._stubs = system_stub.Override(trybot_browser_finder,
                                       ['sys', 'open', 'os'])

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

  def _MockTryserverJson(self, bots_dict):
    trybot_browser_finder.urllib2 = simple_mock.MockObject()
    trybot_browser_finder.urllib2.ExpectCall('urlopen').WithArgs(
        'http://build.chromium.org/p/tryserver.chromium.perf/json').WillReturn(
            StringIO.StringIO(json.dumps({'builders': bots_dict})))

  def test_find_all_browser_types_list(self):
    finder_options = browser_options.BrowserFinderOptions(browser_type='list')
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'mac_10_9_perf_bisect': 'otherstuff',
        'win_perf_bisect_builder': 'not a trybot',
    })
    expected_trybots_list = [
        'trybot-all',
        'trybot-all-android',
        'trybot-all-linux',
        'trybot-all-mac',
        'trybot-all-win',
        'trybot-android-nexus4',
        'trybot-mac-10-9'
    ]

    self.assertEquals(
        expected_trybots_list,
        sorted(trybot_browser_finder.FindAllBrowserTypes(finder_options)))

  def test_find_all_browser_types_trybot(self):
    finder_options = browser_options.BrowserFinderOptions(
        browser_type='trybot-win')
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'mac_10_9_perf_bisect': 'otherstuff',
        'win_perf_bisect_builder': 'not a trybot',
    })
    expected_trybots_list = [
        'trybot-all',
        'trybot-all-android',
        'trybot-all-linux',
        'trybot-all-mac',
        'trybot-all-win',
        'trybot-android-nexus4',
        'trybot-mac-10-9'
    ]
    self.assertEquals(
        expected_trybots_list,
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
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'mac_10_9_perf_bisect': 'otherstuff',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self.assertEquals('android', browser.target_os)
    # pylint: disable=W0212
    self.assertTrue('android' in browser._builder_names)
    self.assertEquals(['android_nexus4_perf_bisect'],
                      browser._builder_names.get('android'))

  def test_constructor_trybot_all(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'android_nexus5_perf_bisect': 'stuff2',
        'mac_10_9_perf_bisect': 'otherstuff',
        'mac_perf_bisect': 'otherstuff1',
        'win_perf_bisect': 'otherstuff2',
        'linux_perf_bisect': 'otherstuff3',
        'win_x64_perf_bisect': 'otherstuff4',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-all', finder_options)
    self.assertEquals('all', browser.target_os)
    # pylint: disable=W0212
    self.assertEquals(
        ['android', 'linux', 'mac', 'win', 'win-x64'],
        sorted(browser._builder_names))
    self.assertEquals(
        ['android_nexus4_perf_bisect', 'android_nexus5_perf_bisect'],
        sorted(browser._builder_names.get('android')))
    self.assertEquals(
        ['mac_10_9_perf_bisect', 'mac_perf_bisect'],
        sorted(browser._builder_names.get('mac')))
    self.assertEquals(
        ['linux_perf_bisect'], sorted(browser._builder_names.get('linux')))
    self.assertEquals(
        ['win_perf_bisect'], sorted(browser._builder_names.get('win')))
    self.assertEquals(
        ['win_x64_perf_bisect'], sorted(browser._builder_names.get('win-x64')))

  def test_constructor_trybot_all_win(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'android_nexus5_perf_bisect': 'stuff2',
        'win_8_perf_bisect': 'otherstuff',
        'win_perf_bisect': 'otherstuff2',
        'linux_perf_bisect': 'otherstuff3',
        'win_x64_perf_bisect': 'otherstuff4',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-all-win', finder_options)
    self.assertEquals('all', browser.target_os)
    # pylint: disable=W0212
    self.assertEquals(
        ['win', 'win-x64'],
        sorted(browser._builder_names))
    self.assertEquals(
        ['win_8_perf_bisect', 'win_perf_bisect'],
        sorted(browser._builder_names.get('win')))
    self.assertEquals(
        ['win_x64_perf_bisect'], sorted(browser._builder_names.get('win-x64')))

  def test_constructor_trybot_all_android(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'android_nexus5_perf_bisect': 'stuff2',
        'win_8_perf_bisect': 'otherstuff',
        'win_perf_bisect': 'otherstuff2',
        'linux_perf_bisect': 'otherstuff3',
        'win_x64_perf_bisect': 'otherstuff4',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-all-android', finder_options)
    self.assertEquals(
        ['android_nexus4_perf_bisect', 'android_nexus5_perf_bisect'],
        sorted(browser._builder_names.get('android')))

  def test_constructor_trybot_all_mac(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'win_8_perf_bisect': 'otherstuff',
        'mac_perf_bisect': 'otherstuff2',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-all-mac', finder_options)
    self.assertEquals('all', browser.target_os)
    # pylint: disable=W0212
    self.assertEquals(
        ['mac'],
        sorted(browser._builder_names))
    self.assertEquals(
        ['mac_perf_bisect'],
        sorted(browser._builder_names.get('mac')))

  def test_constructor_trybot_all_linux(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({
        'android_nexus4_perf_bisect': 'stuff',
        'linux_perf_bisect': 'stuff1',
        'win_8_perf_bisect': 'otherstuff',
        'mac_perf_bisect': 'otherstuff2',
        'win_perf_bisect_builder': 'not a trybot',
    })
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-all-linux', finder_options)
    self.assertEquals('all', browser.target_os)
    # pylint: disable=W0212
    self.assertEquals(
        ['linux'],
        sorted(browser._builder_names))
    self.assertEquals(
        ['linux_perf_bisect'],
        sorted(browser._builder_names.get('linux')))

  def test_no_git(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
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
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
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
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, '', None)),
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, '', None)),
    ))

    browser.RunRemote()
    self.assertEquals(
        ('No local changes found in chromium or blink trees. '
         'browser=trybot-android-nexus4 argument sends local changes to the '
         'perf trybot(s): '
         '[[\'android_nexus4_perf_bisect\']].\n'),
        self.log_output.getvalue())

  def test_branch_checkout_fails(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
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

  def _GetConfigForBrowser(self, name, platform, branch, cfg_filename,
                           is_blink=False):
    finder_options = browser_options.BrowserFinderOptions()
    bot = '%s_perf_bisect' % name.replace('trybot-', '').replace('-', '_')
    self._MockTryserverJson({bot: 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(name, finder_options)
    first_processes = ()
    if is_blink:
      first_processes = (
          (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, 'br', None)),
          (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
          (['git', 'diff-index', 'HEAD'], (0, '', None)),
          (['git', 'log', 'origin/master..HEAD'], (0, '', None))
      )
    self._ExpectProcesses(first_processes + (
        (['git', 'rev-parse', '--abbrev-ref', 'HEAD'], (0, branch, None)),
        (['git', 'update-index', '--refresh', '-q'], (0, None, None,)),
        (['git', 'diff-index', 'HEAD'], (0, '', None)),
        (['git', 'log', 'origin/master..HEAD'], (0, 'logs here', None)),
        (['git', 'checkout', '-b', 'telemetry-tryjob'], (0, None, None)),
        (['git', 'branch', '--set-upstream-to', 'origin/master'],
         (0, None, None)),
        (['git', 'commit', '-a', '-m', 'bisect config: %s' % platform],
         (0, None, None)),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob on %s' % platform],
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
    self._stubs.open.files = {cfg_filename: cfg}

    browser.RunRemote()
    return cfg.getvalue()

  def test_config_android(self):
    config = self._GetConfigForBrowser(
        'trybot-android-nexus4', 'android','somebranch',
        'tools/run-perf-test.cfg')
    self.assertEquals(
        ('config = {\n'
         '  "command": "./tools/perf/run_benchmark '
         '--browser=android-chrome-shell sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "target_arch": "ia32",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

  def test_config_mac(self):
    config = self._GetConfigForBrowser(
        'trybot-mac-10-9', 'mac', 'currentwork', 'tools/run-perf-test.cfg')
    self.assertEquals(
        ('config = {\n'
         '  "command": "./tools/perf/run_benchmark '
         '--browser=release sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "target_arch": "ia32",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

  def test_config_win_x64(self):
    config = self._GetConfigForBrowser(
        'trybot-win-x64', 'win-x64', 'currentwork', 'tools/run-perf-test.cfg')
    self.assertEquals(
        ('config = {\n'
         '  "command": "python tools\\\\perf\\\\run_benchmark '
         '--browser=release_x64 sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "target_arch": "x64",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

  def test_config_blink(self):
    config = self._GetConfigForBrowser(
        'trybot-mac-10-9', 'mac', 'blinkbranch',
        'Tools/run-perf-test.cfg', True)
    self.assertEquals(
        ('config = {\n'
         '  "command": "./tools/perf/run_benchmark '
         '--browser=release sunspider",\n'
         '  "max_time_minutes": "120",\n'
         '  "repeat_count": "1",\n'
         '  "target_arch": "ia32",\n'
         '  "truncate_percent": "0"\n'
         '}'), config)

  def test_update_config_git_commit_tryboterror(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'commit', '-a', '-m', 'bisect config: android'],
         (128, 'None', 'commit failed')),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob on android'],
         (0, 'stuff https://codereview.chromium.org/12345 stuff', None)),
        (['git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b',
          'android_nexus4_perf_bisect'], (0, None, None))))
    self._stubs.sys.argv = [
      'tools/perf/run_benchmark',
      '--browser=%s' % browser,
      'sunspider']
    cfg_filename = 'tools/run-perf-test.cfg'
    cfg = StringIO.StringIO()
    self._stubs.open.files = {cfg_filename: cfg}
    self.assertRaises(trybot_browser_finder.TrybotError,
        browser._UpdateConfigAndRunTryjob, 'android', cfg_filename)

  def test_update_config_git_upload_tryboterror(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'commit', '-a', '-m', 'bisect config: android'],
         (0, 'None', None)),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob on android'],
         (128, None, 'error')),
        (['git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b',
          'android_nexus4_perf_bisect'], (0, None, None))))
    self._stubs.sys.argv = [
      'tools/perf/run_benchmark',
      '--browser=%s' % browser,
      'sunspider']
    cfg_filename = 'tools/run-perf-test.cfg'
    cfg = StringIO.StringIO()
    self._stubs.open.files = {cfg_filename: cfg}
    self.assertRaises(trybot_browser_finder.TrybotError,
        browser._UpdateConfigAndRunTryjob, 'android', cfg_filename)

  def test_update_config_git_try_tryboterror(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'commit', '-a', '-m', 'bisect config: android'],
         (0, 'None', None)),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob on android'],
         (0, 'stuff https://codereview.chromium.org/12345 stuff', None)),
        (['git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b',
          'android_nexus4_perf_bisect'], (128, None, None))))
    self._stubs.sys.argv = [
      'tools/perf/run_benchmark',
      '--browser=%s' % browser,
      'sunspider']
    cfg_filename = 'tools/run-perf-test.cfg'
    cfg = StringIO.StringIO()
    self._stubs.open.files = {cfg_filename: cfg}
    self.assertRaises(trybot_browser_finder.TrybotError,
        browser._UpdateConfigAndRunTryjob, 'android', cfg_filename)

  def test_update_config_git_try(self):
    finder_options = browser_options.BrowserFinderOptions()
    self._MockTryserverJson({'android_nexus4_perf_bisect': 'stuff'})
    browser = trybot_browser_finder.PossibleTrybotBrowser(
        'trybot-android-nexus4', finder_options)
    self._ExpectProcesses((
        (['git', 'commit', '-a', '-m', 'bisect config: android'],
         (0, 'None', None)),
        (['git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
         'CL for perf tryjob on android'],
         (0, 'stuff https://codereview.chromium.org/12345 stuff', None)),
        (['git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b',
          'android_nexus4_perf_bisect'], (0, None, None))))
    self._stubs.sys.argv = [
      'tools/perf/run_benchmark',
      '--browser=%s' % browser,
      'sunspider']
    cfg_filename = 'tools/run-perf-test.cfg'
    cfg = StringIO.StringIO()
    self._stubs.open.files = {cfg_filename: cfg}
    self.assertEquals((0, 'https://codereview.chromium.org/12345'),
        browser._UpdateConfigAndRunTryjob('android', cfg_filename))

