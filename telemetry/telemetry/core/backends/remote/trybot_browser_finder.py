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

from telemetry import decorators
from telemetry.core import platform
from telemetry.core import possible_browser

CHROMIUM_CONFIG_FILENAME = 'tools/run-perf-test.cfg'
BLINK_CONFIG_FILENAME = 'Tools/run-perf-test.cfg'
SUCCESS, NO_CHANGES, ERROR = range(3)


class PossibleTrybotBrowser(possible_browser.PossibleBrowser):
  """A script that sends a job to a trybot."""

  def __init__(self, browser_type, finder_options):
    target_os = browser_type.split('-')[1]
    self._buildername = '%s_perf_bisect' % browser_type.replace(
        'trybot-', '').replace('-', '_')
    super(PossibleTrybotBrowser, self).__init__(browser_type, target_os,
                                                finder_options, True)

  def Create(self):
    raise NotImplementedError()

  def SupportsOptions(self, finder_options):
    if (finder_options.android_device or
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
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    returncode = proc.poll()
    return (returncode, out, err)

  def _AttemptTryjob(self, cfg_file_path):
    """Attempts to run a tryjob from the current directory.

    This is run once for chromium, and if it returns NO_CHANGES, once for blink.

    Args:
      cfg_file_path: Path to the config file for the try job.

    Returns:
      (result, msg) where result is one of:
          SUCCESS if a tryjob was sent
          NO_CHANGES if there was nothing to try,
          ERROR if a tryjob was attempted but an error encountered
          and msg is an error message if an error was encountered, or rietveld
          url if success.
    """
    returncode, original_branchname, err = self._RunProcess(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    if returncode:
      msg = 'Must be in a git repository to send changes to trybots.'
      if err:
        msg += '\nGit error: %s' % err
      return (ERROR, msg)
    original_branchname = original_branchname.strip()

    # Check if the tree is dirty: make sure the index is up to date and then
    # run diff-index
    self._RunProcess(['git', 'update-index', '--refresh', '-q'])
    returncode, out, err = self._RunProcess(['git', 'diff-index', 'HEAD'])
    if out:
      msg = 'Cannot send a try job with a dirty tree. Commit locally first.'
      return (ERROR, msg)

    # Make sure the tree does have local commits.
    returncode, out, err = self._RunProcess(
        ['git', 'log', 'origin/master..HEAD'])
    if not out:
      return (NO_CHANGES, None)

    # Create/check out the telemetry-tryjob branch, and edit the configs
    # for the tryjob there.
    returncode, out, err = self._RunProcess(
        ['git', 'checkout', '-b', 'telemetry-tryjob'])
    if returncode:
      msg = ('Error creating branch telemetry-tryjob. '
             'Please delete it if it exists.\n%s' % err)
      return (ERROR, msg)
    returncode, out, err = self._RunProcess(
        ['git', 'branch', '--set-upstream-to', 'origin/master'])
    if returncode:
      return (ERROR, 'Error in git branch --set-upstream-to: %s' % err)

    # Generate the command line for the perf trybots
    arguments = sys.argv
    if self._target_os == 'win':
      arguments[0] = 'python tools\\perf\\run_measurement'
    else:
      arguments[0] = './tools/perf/run_measurement'
    for index, arg in enumerate(arguments):
      if arg.startswith('--browser='):
        if self._target_os == 'android':
          arguments[index] = '--browser=android-chrome-shell'
        else:
          arguments[index] = '--browser=release'
    command = ' '.join(arguments)

    # Add the correct command to the config file and commit it.
    config = {
        'command': command,
        'repeat_count': '1',
        'max_time_minutes': '120',
        'truncate_percent': '0',
    }
    try:
      config_file = open(cfg_file_path, 'w')
    except IOError:
      msg = 'Cannot find %s. Please run from src dir.' % cfg_file_path
      return (ERROR, msg)
    config_file.write('config = %s' % json.dumps(
        config, sort_keys=True, indent=2, separators=(',', ': ')))
    config_file.close()
    returncode, out, err = self._RunProcess(
        ['git', 'commit', '-a', '-m', 'bisect config'])
    if returncode:
      msg = 'Could not commit bisect config change, error %s' % err
      return (ERROR, msg)

    # Upload the CL to rietveld and run a try job.
    returncode, out, err = self._RunProcess([
        'git', 'cl', 'upload', '-f', '--bypass-hooks', '-m',
        'CL for perf tryjob'
    ])
    if returncode:
      msg = 'Could upload to rietveld, error %s' % err
      return (ERROR, msg)
    match = re.search(r'https://codereview.chromium.org/[\d]+', out)
    if not match:
      msg = 'Could not upload CL to rietveld! Output %s' % out
      return (ERROR, msg)
    rietveld_url = match.group(0)
    returncode, out, err = self._RunProcess([
        'git', 'cl', 'try', '-m', 'tryserver.chromium.perf', '-b',
        self._buildername])
    if returncode:
      msg = 'Could not try CL, error %s' % err
      return (ERROR, msg)

    # Checkout original branch and delete telemetry-tryjob branch.
    returncode, out, err = self._RunProcess(
        ['git', 'checkout', original_branchname])
    if returncode:
      msg = (
          ('Could not check out %s. Please check it out and manually '
           'delete the telemetry-tryjob branch. Error message: %s') %
          (original_branchname, err))
      return (ERROR, msg)
    returncode, out, err = self._RunProcess(
        ['git', 'branch', '-D', 'telemetry-tryjob'])
    if returncode:
      msg = (('Could not delete telemetry-tryjob branch. '
              'Please delete it manually. Error %s') % err)
      return (ERROR, msg)
    return (SUCCESS, rietveld_url)

  def RunRemote(self):
    """Sends a tryjob to a perf trybot.

    This creates a branch, telemetry-tryjob, switches to that branch, edits
    the bisect config, commits it, uploads the CL to rietveld, and runs a
    tryjob on the given bot.
    """
    # First check if there are chromium changes to upload.
    status, msg = self._AttemptTryjob(CHROMIUM_CONFIG_FILENAME)
    if status == SUCCESS:
      print 'Uploaded chromium try job to rietveld. View progress at %s' % msg
      return
    elif status == ERROR:
      logging.error(msg)
      return

    # If we got here, there are no chromium changes to upload. Try blink.
    os.chdir('third_party/WebKit/')
    status, msg = self._AttemptTryjob(BLINK_CONFIG_FILENAME)
    os.chdir('../..')
    if status == SUCCESS:
      print 'Uploaded blink try job to rietveld. View progress at %s' % msg
      return
    elif status == ERROR:
      logging.error(msg)
      return
    else:
      logging.error('No local changes found in chromium or blink trees. '
                    'browser=%s argument sends local changes to the %s '
                    'perf trybot.', self._browser_type, self._buildername)
      return

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
  builders = ['trybot-%s' % b.replace('_perf_bisect', '').replace('_', '-')
              for b in builders if not b.endswith('_perf_bisect_builder')]
  # Perf try jobs do not work on Windows XP
  if 'trybot-win-xp' in builders:
    builders.remove('trybot-win-xp')
  return builders


def FindAllBrowserTypes(finder_options):
  # Listing browsers requires an http request; only do this if the user is
  # running with browser=list or a browser=trybot-* argument.
  if (finder_options.browser_type and
      (finder_options.browser_type == 'list' or
       finder_options.browser_type.startswith('trybot'))):
    return _GetTrybotList()
  return []


def FindAllAvailableBrowsers(finder_options):
  """Find all perf trybots on tryserver.chromium.perf."""
  return [PossibleTrybotBrowser(b, finder_options) for b in
          FindAllBrowserTypes(finder_options)]
