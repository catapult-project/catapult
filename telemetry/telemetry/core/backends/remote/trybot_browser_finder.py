# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds perf trybots that can run telemetry tests."""

import json
import logging
import os
import re
import subprocess
import sys
import urllib2

from telemetry.core import platform
from telemetry.core.platform import trybot_device
from telemetry.core import possible_browser
from telemetry import decorators

CHROMIUM_CONFIG_FILENAME = 'tools/run-perf-test.cfg'
BLINK_CONFIG_FILENAME = 'Tools/run-perf-test.cfg'
SUCCESS, NO_CHANGES, ERROR = range(3)
# Unsupported Perf bisect bots.
EXCLUDED_BOTS = {
    'win_xp_perf_bisect',
    'linux_perf_tester',
    'linux_perf_bisector',
    'win_perf_bisect_builder',
    'win_x64_perf_bisect_builder',
    'linux_perf_bisect_builder',
    'mac_perf_bisect_builder',
    'android_perf_bisect_builder'
}

INCLUDE_BOTS = [
    'trybot-all',
    'trybot-all-win',
    'trybot-all-mac',
    'trybot-all-linux',
    'trybot-all-android'
]

class TrybotError(Exception):

  def __str__(self):
    return '%s\nError running tryjob.' % self.args[0]


class PossibleTrybotBrowser(possible_browser.PossibleBrowser):
  """A script that sends a job to a trybot."""

  def __init__(self, browser_type, _):
    target_os = browser_type.split('-')[1]
    self._builder_names = _GetBuilderNames(browser_type)
    super(PossibleTrybotBrowser, self).__init__(browser_type, target_os, True)

  def Create(self, finder_options):
    raise NotImplementedError()

  def SupportsOptions(self, finder_options):
    if ((finder_options.device and finder_options.device != 'trybot') or
        finder_options.chrome_root or
        finder_options.cros_remote or
        finder_options.extensions_to_load or
        finder_options.interactive or
        finder_options.profile_dir):
      return False
    return True

  def IsRemote(self):
    return True

  def _RunProcess(self, cmd):
    logging.debug('Running process: "%s"', ' '.join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    returncode = proc.poll()
    return (returncode, out, err)

  def _UpdateConfigAndRunTryjob(self, bot_platform, cfg_file_path):
    """Updates perf config file, uploads changes and excutes perf try job.

    Args:
      bot_platform: Name of the platform to be generated.
      cfg_file_path: Perf config file path.

    Returns:
      (result, msg) where result is one of:
          SUCCESS if a tryjob was sent
          NO_CHANGES if there was nothing to try,
          ERROR if a tryjob was attempted but an error encountered
          and msg is an error message if an error was encountered, or rietveld
          url if success, otherwise throws TrybotError exception.
    """
    config = self._GetPerfConfig(bot_platform)
    try:
      config_file = open(cfg_file_path, 'w')
    except IOError:
      msg = 'Cannot find %s. Please run from src dir.' % cfg_file_path
      return (ERROR, msg)
    config_file.write('config = %s' % json.dumps(
        config, sort_keys=True, indent=2, separators=(',', ': ')))
    config_file.close()
    # Commit the config changes locally.
    returncode, out, err = self._RunProcess(
        ['git', 'commit', '-a', '-m', 'bisect config: %s' % bot_platform])
    if returncode:
      raise TrybotError('Could not commit bisect config change for %s,'
                        ' error %s' % (bot_platform, err))
    # Upload the CL to rietveld and run a try job.
    returncode, out, err = self._RunProcess([
        'git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
        'CL for perf tryjob on %s' % bot_platform
    ])
    if returncode:
      raise TrybotError('Could upload to rietveld for %s, error %s' %
                        (bot_platform, err))

    match = re.search(r'https://codereview.chromium.org/[\d]+', out)
    if not match:
      raise TrybotError('Could not upload CL to rietveld for %s! Output %s' %
                        (bot_platform, out))
    rietveld_url = match.group(0)
    # Generate git try command for available bots.
    git_try_command = ['git', 'cl', 'try', '-m', 'tryserver.chromium.perf']
    for bot in self._builder_names[bot_platform]:
      git_try_command.extend(['-b', bot])
    returncode, out, err = self._RunProcess(git_try_command)
    if returncode:
      raise TrybotError('Could not try CL for %s, error %s' %
                        (bot_platform, err))

    return (SUCCESS, rietveld_url)

  def _GetPerfConfig(self, bot_platform):
    """Generates the perf config for try job.

    Args:
      bot_platform: Name of the platform to be generated.

    Returns:
      A dictionary with perf config parameters.
    """
    # Generate the command line for the perf trybots
    target_arch = 'ia32'
    arguments = sys.argv
    if bot_platform in ['win', 'win-x64']:
      arguments[0] = 'python tools\\perf\\run_benchmark'
    else:
      arguments[0] = './tools/perf/run_benchmark'
    for index, arg in enumerate(arguments):
      if arg.startswith('--browser='):
        if bot_platform == 'android':
          arguments[index] = '--browser=android-chrome-shell'
        elif any('x64' in bot for bot in self._builder_names[bot_platform]):
          arguments[index] = '--browser=release_x64'
          target_arch = 'x64'
        else:
          arguments[index] = '--browser=release'
    command = ' '.join(arguments)

    return {
        'command': command,
        'repeat_count': '1',
        'max_time_minutes': '120',
        'truncate_percent': '0',
        'target_arch': target_arch,
    }

  def _AttemptTryjob(self, cfg_file_path):
    """Attempts to run a tryjob from the current directory.

    This is run once for chromium, and if it returns NO_CHANGES, once for blink.

    Args:
      cfg_file_path: Path to the config file for the try job.

    Returns:
      Returns SUCCESS if a tryjob was sent, NO_CHANGES if there was nothing to
      try, ERROR if a tryjob was attempted but an error encountered.
    """
    source_repo = 'chromium'
    if cfg_file_path == BLINK_CONFIG_FILENAME:
      source_repo = 'blink'

    # TODO(prasadv): This method is quite long, we should consider refactor
    # this by extracting to helper methods.
    returncode, original_branchname, err = self._RunProcess(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    if returncode:
      msg = 'Must be in a git repository to send changes to trybots.'
      if err:
        msg += '\nGit error: %s' % err
      logging.error(msg)
      return ERROR

    original_branchname = original_branchname.strip()

    # Check if the tree is dirty: make sure the index is up to date and then
    # run diff-index
    self._RunProcess(['git', 'update-index', '--refresh', '-q'])
    returncode, out, err = self._RunProcess(['git', 'diff-index', 'HEAD'])
    if out:
      logging.error(
          'Cannot send a try job with a dirty tree. Commit locally first.')
      return ERROR

    # Make sure the tree does have local commits.
    returncode, out, err = self._RunProcess(
        ['git', 'log', 'origin/master..HEAD'])
    if not out:
      return NO_CHANGES

    # Create/check out the telemetry-tryjob branch, and edit the configs
    # for the tryjob there.
    returncode, out, err = self._RunProcess(
        ['git', 'checkout', '-b', 'telemetry-tryjob'])
    if returncode:
      logging.error('Error creating branch telemetry-tryjob. '
                    'Please delete it if it exists.\n%s', err)
      return ERROR
    try:
      returncode, out, err = self._RunProcess(
          ['git', 'branch', '--set-upstream-to', 'origin/master'])
      if returncode:
        logging.error('Error in git branch --set-upstream-to: %s', err)
        return ERROR
      for bot_platform in self._builder_names:
        try:
          results, output = self._UpdateConfigAndRunTryjob(
              bot_platform, cfg_file_path)
          if results == ERROR:
            logging.error(output)
            return ERROR
          print ('Uploaded %s try job to rietveld for %s platform. '
                 'View progress at %s' % (source_repo, bot_platform, output))
        except TrybotError, err:
          print err
          logging.error(err)
    finally:
      # Checkout original branch and delete telemetry-tryjob branch.
      # TODO(prasadv): This finally block could be extracted out to be a
      # separate function called _CleanupBranch.
      returncode, out, err = self._RunProcess(
          ['git', 'checkout', original_branchname])
      if returncode:
        logging.error('Could not check out %s. Please check it out and '
                      'manually delete the telemetry-tryjob branch. '
                      ': %s', original_branchname, err)
        return ERROR # pylint: disable=lost-exception
      logging.info('Checked out original branch: %s', original_branchname)
      returncode, out, err = self._RunProcess(
          ['git', 'branch', '-D', 'telemetry-tryjob'])
      if returncode:
        logging.error('Could not delete telemetry-tryjob branch. '
                      'Please delete it manually: %s', err)
        return ERROR # pylint: disable=lost-exception
      logging.info('Deleted temp branch: telemetry-tryjob')
    return SUCCESS

  def RunRemote(self):
    """Sends a tryjob to a perf trybot.

    This creates a branch, telemetry-tryjob, switches to that branch, edits
    the bisect config, commits it, uploads the CL to rietveld, and runs a
    tryjob on the given bot.
    """
    # First check if there are chromium changes to upload.
    status = self._AttemptTryjob(CHROMIUM_CONFIG_FILENAME)
    if status not in [SUCCESS, ERROR]:
      # If we got here, there are no chromium changes to upload. Try blink.
      os.chdir('third_party/WebKit/')
      status = self._AttemptTryjob(BLINK_CONFIG_FILENAME)
      os.chdir('../..')
      if status not in [SUCCESS, ERROR]:
        logging.error('No local changes found in chromium or blink trees. '
                      'browser=%s argument sends local changes to the '
                      'perf trybot(s): %s.', self.browser_type,
                      self._builder_names.values())

  def _InitPlatformIfNeeded(self):
    if self._platform:
      return

    self._platform = platform.GetHostPlatform()

    # pylint: disable=W0212
    self._platform_backend = self._platform._platform_backend


def SelectDefaultBrowser(_):
  return None


def CanFindAvailableBrowsers():
  return True


@decorators.Cache
def _GetTrybotList():
  f = urllib2.urlopen(
      'http://build.chromium.org/p/tryserver.chromium.perf/json')
  builders = json.loads(f.read()).get('builders', {}).keys()
  builders = ['trybot-%s' % bot.replace('_perf_bisect', '').replace('_', '-')
              for bot in builders if bot not in EXCLUDED_BOTS]
  builders.extend(INCLUDE_BOTS)
  return sorted(builders)


def _GetBuilderNames(browser_type):
  """ Return platform and its available bot name as dictionary."""
  if 'all' not in browser_type:
    bot = ['%s_perf_bisect' % browser_type.replace(
        'trybot-', '').replace('-', '_')]
    bot_platform = browser_type.split('-')[1]
    if 'x64' in browser_type:
      bot_platform += '-x64'
    return {bot_platform: bot}

  f = urllib2.urlopen(
      'http://build.chromium.org/p/tryserver.chromium.perf/json')
  builders = json.loads(f.read()).get('builders', {}).keys()
  # Exclude unsupported bots like win xp and some dummy bots.
  builders = [bot for bot in builders if bot not in EXCLUDED_BOTS]

  platform_and_bots = {}
  for os_name in ['linux', 'android', 'mac', 'win']:
    platform_and_bots[os_name] = [bot for bot in builders if os_name in bot]

  # Special case for Windows x64, consider it as separate platform
  # config config should contain target_arch=x64 and --browser=release_x64.
  win_x64_bots = [platform_and_bots['win'].pop(i)
      for i, win_bot in enumerate(platform_and_bots['win']) if 'x64' in win_bot]
  platform_and_bots['win-x64'] = win_x64_bots

  if 'all-win' in browser_type:
    return {'win': platform_and_bots['win'],
            'win-x64': platform_and_bots['win-x64']}
  if 'all-mac' in browser_type:
    return {'mac': platform_and_bots['mac']}
  if 'all-android' in browser_type:
    return {'android': platform_and_bots['android']}
  if 'all-linux' in browser_type:
    return {'linux': platform_and_bots['linux']}

  return platform_and_bots


def FindAllBrowserTypes(finder_options):
  # Listing browsers requires an http request; only do this if the user is
  # running with browser=list or a browser=trybot-* argument.
  if (finder_options.browser_type and
      (finder_options.browser_type == 'list' or
       finder_options.browser_type.startswith('trybot'))):
    return _GetTrybotList()
  return []


def FindAllAvailableBrowsers(finder_options, device):
  """Find all perf trybots on tryserver.chromium.perf."""
  if not isinstance(device, trybot_device.TrybotDevice):
    return []

  return [PossibleTrybotBrowser(b, finder_options) for b in
          FindAllBrowserTypes(finder_options)]
