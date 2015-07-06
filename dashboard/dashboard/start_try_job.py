# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint containing server-side functionality for bisect try jobs."""

import difflib
import hashlib
import json
import re

import httplib2

from google.appengine.api import users

from dashboard import buildbucket_job
from dashboard import buildbucket_service
from dashboard import quick_logger
from dashboard import request_handler
from dashboard import rietveld_service
from dashboard import update_test_metadata
from dashboard import utils
from dashboard.models import graph_data
from dashboard.models import try_job


# Path to the perf bisect script config file, relative to chromium/src.
_BISECT_CONFIG_PATH = 'tools/auto_bisect/bisect.cfg'

# Path to the perf trybot config file, relative to chromium/src.
_PERF_CONFIG_PATH = 'tools/run-perf-test.cfg'

_PATCH_HEADER = """Index: %(filename)s
diff --git a/%(filename_a)s b/%(filename_b)s
index %(hash_a)s..%(hash_b)s 100644
"""

# These should be kept consistent with the constants used in auto-bisect.
_PERF_BUILDER_TYPE = 'perf'

# A set of suites for which we can't do performance bisects.
# This list currently also exists in elements/bisect-button.html.
_UNBISECTABLE_SUITES = [
    'arc-perf-test',
    'audio-e2e-test',
    'audioproc_perf',
    'browser_tests',
    'endure',
    'isac_fixed_perf',
    'mach_ports',
    'media_tests_av_perf',
    'page_cycler_2012Q2-netsim',
    'pyauto_webrtc_quality_tests',
    'pyauto_webrtc_tests',
    'scroll_telemetry_top_25',
    'sizes',
    'startup_test',
    'vie_auto_test',
    'webrtc_manual_browser_tests_test',
    'webrtc_perf_content_unittests_test',
    'webrtc_pyauto_quality',
    'webrtc_pyauto',
]

# Available bisect bots on tryserver.chromium.perf waterfall.
_BISECT_BOTS = [
    'android_motoe_perf_bisect',
    'android_nexus4_perf_bisect',
    'android_nexus5_perf_bisect',
    'android_nexus6_perf_bisect',
    'android_nexus7_perf_bisect',
    'android_nexus9_perf_bisect',
    'android_nexus10_perf_bisect',
    'linux_perf_bisect',
    'mac_perf_bisect',
    'mac_10_9_perf_bisect',
    'win_perf_bisect',
    'win_x64_perf_bisect',
    'win_x64_ati_gpu_perf_bisect',
    'win_x64_nvidia_gpu_perf_bisect',
    'win_xp_perf_bisect',
    'win_8_perf_bisect',
]


class StartBisectHandler(request_handler.RequestHandler):
  """URL endpoint for AJAX requests for bisect config handling.

  Requests are made to /bisect by the bisect-form Polymer element for a few
  different types of data. This handler returns three different types of output
  depending on the value of the 'step' parameter posted. In the order that
  they're requested in the process of using the bisect button feature:
    (1) prefill-info: Returns JSON with some info to fill into the initial form.
    (2) get-config: Returns text to fill in for the bisect job config.
    (3) perform-bisect: Send a patch to Rietveld to start a bisect job.
  """

  def post(self):
    """Performs one of several bisect-related actions depending on parameters.

    The only required parameter is "step", which indicates which action is to
    be performed.

    Outputs JSON, with different information depending on "step".
    """
    user = users.get_current_user()
    if not user:
      self.response.out.write(json.dumps({
          'error': 'You must be logged in to run a bisect job.'}))
      return
    if (not user.email().endswith('google.com') and
        not user.email().endswith('chromium.org')):
      # Require a login from the start so we don't forget when we add support
      # for actually kicking off bisect jobs.
      self.response.out.write(json.dumps({
          'error': ('You must be logged in to either a chromium.org'
                    ' or google.com account to run a bisect job.')}))
      return

    step = self.request.get('step')

    if step == 'prefill-info':
      result = _PrefillInfo(self.request.get('test_path'))
    elif step == 'perform-bisect':
      bisect_config = GetBisectConfig(self.request.get('bisect_bot'),
                                      self.request.get('suite'),
                                      self.request.get('metric'),
                                      self.request.get('good_revision'),
                                      self.request.get('bad_revision'),
                                      self.request.get('repeat_count', 10),
                                      self.request.get('max_time_minutes', 20),
                                      self.request.get('truncate_percent', 25),
                                      self.request.get('bug_id', -1),
                                      self.request.get('use_archive'),
                                      self.request.get('bisect_mode', 'mean'))
      if not bisect_config.get('error'):
        bug_id = self.request.get('bug_id', None)
        if bug_id:
          bug_id = int(bug_id)

        master_name = self.request.get('master', 'ChromiumPerf')
        internal_only = False
        if self.request.get('internal_only') == 'true':
          internal_only = True

        use_buildbucket = self.request.get('use_recipe') == 'true'
        bisect_job = try_job.TryJob(bot=self.request.get('bisect_bot'),
                                    config=bisect_config.get('config'),
                                    bug_id=bug_id,
                                    email=user.email(),
                                    master_name=master_name,
                                    internal_only=internal_only,
                                    job_type='bisect',
                                    use_buildbucket=use_buildbucket)

        try:
          result = PerformBisect(bisect_job)
        except request_handler.InvalidInputError as iie:
          result = {'error': iie.message}
      else:
        result = bisect_config
    elif step == 'perform-perf-try':
      perf_config = _GetPerfTryConfig(self.request.get('bisect_bot'),
                                      self.request.get('suite'),
                                      self.request.get('good_revision'),
                                      self.request.get('bad_revision'),
                                      self.request.get('rerun_option'))
      if not perf_config.get('error'):
        perf_job = try_job.TryJob(bot=self.request.get('bisect_bot'),
                                  config=perf_config.get('config'),
                                  bug_id=-1,
                                  email=user.email(),
                                  job_type='perf-try')
        result = _PerformPerfTryJob(perf_job)
      else:
        result = perf_config
    else:
      result = {'error': 'Invalid parameters.'}

    self.response.write(json.dumps(result))


def _PrefillInfo(test_path):
  """Pre-fills some best guesses config form based on the test path.

  Args:
    test_path: Test path string.

  Returns:
    A dictionary indicating the result. If successful, this should contain the
    the fields "suite", "email", "all_metrics", and "default_metric". If not
    successful this will contain the field "error".
  """
  if not test_path:
    return {'error': 'No test specified'}

  suite_path = '/'.join(test_path.split('/')[:3])
  suite = utils.TestKey(suite_path).get()
  if not suite:
    return {'error': 'Invalid test %s' % test_path}

  graph_path = '/'.join(test_path.split('/')[:4])
  graph_key = utils.TestKey(graph_path)

  info = {'suite': suite.key.string_id()}
  info['master'] = suite.master_name
  info['internal_only'] = suite.internal_only
  info['use_archive'] = _CanDownloadBuilds(suite.master_name)

  info['all_bots'] = _BISECT_BOTS
  info['bisect_bot'] = GuessBisectBot(suite.bot.string_id())

  user = users.get_current_user()
  if not user:
    return {'error': 'User not logged in.'}

  # Secondary check for bisecting internal only tests.
  if suite.internal_only and not request_handler.IsLoggedInWithGoogleAccount():
    return {'error': 'Unauthorized access, please use corp account to login.'}

  info['email'] = user.email()

  info['all_metrics'] = []
  metric_keys_query = graph_data.Test.query(
      graph_data.Test.has_rows == True, ancestor=graph_key)
  metric_keys = metric_keys_query.fetch(keys_only=True)
  for metric_key in metric_keys:
    metric_path = utils.TestPath(metric_key)
    if metric_path.endswith('/ref') or metric_path.endswith('_ref'):
      continue
    info['all_metrics'].append(GuessMetric(metric_path))
  info['default_metric'] = GuessMetric(test_path)

  return info


def _IsGitHash(revision):
  git_pattern = re.compile(r'[a-fA-F0-9]{40}$')
  return git_pattern.match(str(revision))


def GetBisectConfig(bisect_bot, suite, metric, good_revision, bad_revision,
                    repeat_count, max_time_minutes, truncate_percent, bug_id,
                    use_archive=None, bisect_mode='mean'):
  """Fills in a JSON response with the filled-in config file.

  Args:
    bisect_bot: Bisect bot name.
    suite: Test suite name.
    metric: Bisect bot "metric" parameter, in the form "chart/trace".
    good_revision: Known good revision number.
    bad_revision: Known bad revision number.
    repeat_count: Number of times to repeat the test.
    max_time_minutes: Max time to run the test.
    truncate_percent: How many high and low values to discard.
    bug_id: The Chromium issue tracker bug ID.
    use_archive: Specifies whether to use build archives or not to bisect.
        If this is not empty or None, then we want to use archived builds.
    bisect_mode: What aspect of the test run to bisect on; possible options are
        "mean", "std_dev", and "return_code".

  Returns:
    A dictionary with the result; if successful, this will contain "config",
    which is a config string; if there's an error, this will contain "error".
  """
  command = GuessCommand(bisect_bot, suite, metric=metric)

  try:
    if not _IsGitHash(good_revision):
      good_revision = int(good_revision)
    if not _IsGitHash(bad_revision):
      bad_revision = int(bad_revision)
    repeat_count = int(repeat_count)
    max_time_minutes = int(max_time_minutes)
    truncate_percent = int(truncate_percent)
    bug_id = int(bug_id)
  except ValueError:
    return {'error': ('repeat count, max time, and truncate percent '
                      'must all be integers and revision as git hash or int.')}

  can_bisect_result = CheckBisectability(good_revision, bad_revision,
                                         bot=bisect_bot)
  if can_bisect_result is not None:
    return can_bisect_result

  builder_type = ''
  if use_archive:
    builder_type = _PERF_BUILDER_TYPE

  config_dict = {
      'command': command,
      'good_revision': str(good_revision),
      'bad_revision': str(bad_revision),
      'metric': metric,
      'repeat_count': str(repeat_count),
      'max_time_minutes': str(max_time_minutes),
      'truncate_percent': str(truncate_percent),
      'bug_id': str(bug_id),
      'builder_type': builder_type,
      'target_arch': 'x64' if 'x64' in bisect_bot else 'ia32',
      'bisect_mode': bisect_mode,
  }
  config_python_string = 'config = %s\n' % json.dumps(
      config_dict, sort_keys=True, indent=2, separators=(',', ': '))
  return {'config': config_python_string, 'config_dict': config_dict}


def _GetPerfTryConfig(
    bisect_bot, suite, good_revision, bad_revision, rerun_option=None):
  """Fills in a JSON response with the filled-in config file.

  Args:
    bisect_bot: Bisect bot name.
    suite: Test suite name.
    good_revision: Known good revision number.
    bad_revision: Known bad revision number.
    rerun_option: Optional rerun command line parameter.

  Returns:
    A dictionary with the result; if successful, this will contain "config",
    which is a config string; if there's an error, this will contain "error".
  """
  command = GuessCommand(bisect_bot, suite, rerun_option=rerun_option)
  if not command:
    return {'error': 'Only telemetry is supported at the moment.'}

  try:
    if not _IsGitHash(good_revision):
      good_revision = int(good_revision)
    if not _IsGitHash(bad_revision):
      bad_revision = int(bad_revision)
  except ValueError:
    return {'error': ('revisions must be git hashes or integers.')}

  can_bisect_result = CheckBisectability(good_revision, bad_revision,
                                         bot=bisect_bot)
  if can_bisect_result is not None:
    return can_bisect_result

  config_dict = {
      'command': command,
      'good_revision': str(good_revision),
      'bad_revision': str(bad_revision),
      'repeat_count': '1',
      'max_time_minutes': '60',
      'truncate_percent': '0',
  }
  config_python_string = 'config = %s\n' % json.dumps(
      config_dict, sort_keys=True, indent=2, separators=(',', ': '))
  return {'config': config_python_string}


def _CanDownloadBuilds(master_name):
  """Check whether bisecting using archives is supported."""
  return master_name == 'ChromiumPerf'


def GuessBisectBot(bot_name):
  """Returns a bisect bot name based on |bot_name| (perf_id) string."""
  bot_name = bot_name.lower()

  # Specific platforms which have an exact matching bisect bot.
  #
  # TODO(tonyg): This mapping shouldn't be hardcoded in the dashboard. That's
  # likely best fixed by achieving full coverage and switching to a predictable
  # naming pattern.
  platform_bots = [
      ('linux', 'linux_perf_bisect'),
      ('mac8', 'mac_perf_bisect'),
      ('mac9', 'mac_10_9_perf_bisect'),
      ('motoe', 'android_motoe_perf_bisect'),
      ('one', 'android_one_perf_bisect'),
      ('nexus4', 'android_nexus4_perf_bisect'),
      ('nexus5', 'android_nexus5_perf_bisect'),
      ('nexus6', 'android_nexus6_perf_bisect'),
      ('nexus7', 'android_nexus7_perf_bisect'),
      ('nexus9', 'android_nexus9_perf_bisect'),
      ('nexus10', 'android_nexus10_perf_bisect'),
      ('win7-gpu-ati', 'win_x64_ati_gpu_perf_bisect'),
      ('win7-gpu-nvidia', 'win_x64_nvidia_gpu_perf_bisect'),
      ('win7-x64', 'win_x64_perf_bisect'),
      ('win7', 'win_perf_bisect'),
      ('win8', 'win_8_perf_bisect'),
      ('xp', 'win_xp_perf_bisect'),
  ]
  # Fallbacks to related platforms when there's no exact match (with a
  # preference for historically reliable platforms).
  platform_fallbacks = [
      ('android', 'android_nexus10_perf_bisect'),
      ('linux', 'linux_perf_bisect'),
      ('mac', 'mac_perf_bisect'),
      ('win', 'win_perf_bisect'),
  ]

  # Last resort fallback to the most reliable bisector (but totally unrelated).
  fallback = 'linux_perf_bisect'

  for platform, bisect_bot in platform_bots + platform_fallbacks:
    if platform in bot_name:
      return bisect_bot
  return fallback


# TODO(qyearsley): Use metric to add a --story-filter flag for Telemetry.
# See: http://crbug.com/448628
def GuessCommand(bisect_bot, suite, metric=None, rerun_option=None):  # pylint: disable=unused-argument
  """Returns a command to use in the bisect configuration."""
  platform = bisect_bot.split('_')[0]

  non_telemetry_tests = {
      'angle_perftests': [
          './out/Release/angle_perftests',
          '--test-launcher-print-test-stdio=always',
          '--test-launcher-jobs=1',
      ],
      'cc_perftests': [
          './out/Release/cc_perftests',
          '--test-launcher-print-test-stdio=always',
      ],
      'idb_perf': [
          './out/Release/performance_ui_tests',
          '--gtest_filter=IndexedDBTest.Perf',
      ],
      'load_library_perf_tests': [
          './out/Release/load_library_perf_tests',
          '--single-process-tests',
      ],
      'media_perftests': [
          './out/Release/media_perftests',
          '--single-process-tests',
      ],
      'performance_browser_tests': [
          './out/Release/performance_browser_tests',
          '--test-launcher-print-test-stdio=always',
          '--enable-gpu',
      ],
  }

  if suite == 'cc_perftests' and platform == 'android':
    return 'build/android/test_runner.py gtest --release -s cc_perftests'
  if suite in non_telemetry_tests:
    command = non_telemetry_tests[suite]
    if platform == 'win':
      command[0] = command[0].replace('/', '\\')
      command[0] += '.exe'
    return ' '.join(command)

  command = []

  # On Windows, Python scripts should be prefixed with the python command.
  if platform == 'win':
    command.append('python')

  command.append('tools/perf/run_benchmark')
  command.append('-v')

  # For Telemetry tests, we need to specify the browser,
  # and the browser to use may depend on the platform.
  if platform == 'android':
    # Prior to crrev.com/274857 *only* android-chromium-testshell
    # Then until crrev.com/276628 *both* (android-chromium-testshell and
    # android-chrome-shell) work. After that revision *only*
    # android-chrome-shell works. bisect-perf-reggresion.py script should
    # handle these cases and set appropriate browser type based on revision,
    # dashboard will always set to 'android-chrome-shell' since it sets for
    # revision range not per revision.
    browser = 'android-chrome-shell'
  else:
    browser = 'release'
  command.append('--browser=%s' % browser)

  # Some tests require a pre-generated Chrome profile.
  uses_profile = (
      suite == 'startup.warm.dirty.blank_page' or
      suite == 'startup.cold.dirty.blank_page' or
      suite.startswith('session_restore'))
  if uses_profile:
    # Profile directory relative to chromium/src.
    profile_dir = 'out/Release/generated_profile/small_profile'
    command.append('--profile-dir=%s' % profile_dir)

  # Test command might be a little different from the test name on the bots.
  if suite == 'blink_perf':
    test_name = 'blink_perf.all'
  elif suite == 'startup.cold.dirty.blank_page':
    test_name = 'startup.cold.blank_page'
  elif suite == 'startup.warm.dirty.blank_page':
    test_name = 'startup.warm.blank_page'
  else:
    test_name = suite
  command.append(test_name)

  if rerun_option:
    command.append(rerun_option)

  return ' '.join(command)


def GuessMetric(test_path):
  """Returns a "metric" name used in the bisect config.

  Generally, but not always, this "metric" is the chart name and trace name
  separated by a slash.

  Args:
    test_path: The slash-separated test path used by the dashboard.

  Returns:
    A "metric" used by the bisect bot, generally of the from graph/trace.
  """
  parts = test_path.split('/')
  graph_trace = parts[3:]
  if len(graph_trace) == 1:
    graph_trace.append(graph_trace[0])

  return '/'.join(graph_trace)


def _CreatePatch(base_config, config_changes, config_path):
  """Takes the base config file and the changes and generates a patch.

  Args:
    base_config: The whole contents of the base config file.
    config_changes: The new config string. This will replace the part of the
        base config file that starts with "config = {" and ends with "}".
    config_path: Path to the config file to use.

  Returns:
    A triple with the patch string, the base md5 checksum, and the "base
    hashes", which normally might contain checksums for multiple files, but
    in our case just contains the base checksum and base filename.
  """
  # Compute git SHA1 hashes for both the original and new config. See:
  # http://git-scm.com/book/en/Git-Internals-Git-Objects#Object-Storage
  base_checksum = hashlib.md5(base_config).hexdigest()
  base_hashes = '%s:%s' % (base_checksum, config_path)
  base_header = 'blob %d\0' % len(base_config)
  base_sha = hashlib.sha1(base_header + base_config).hexdigest()

  # Replace part of the base config to get the new config.
  new_config = (base_config[:base_config.rfind('config')] +
                config_changes +
                base_config[base_config.rfind('}') + 2:])

  # The client sometimes adds extra '\r' chars; remove them.
  new_config = new_config.replace('\r', '')
  new_header = 'blob %d\0' % len(new_config)
  new_sha = hashlib.sha1(new_header + new_config).hexdigest()
  diff = difflib.unified_diff(base_config.split('\n'),
                              new_config.split('\n'),
                              'a/%s' % config_path,
                              'b/%s' % config_path,
                              lineterm='')
  patch_header = _PATCH_HEADER % {
      'filename': config_path,
      'filename_a': config_path,
      'filename_b': config_path,
      'hash_a': base_sha,
      'hash_b': new_sha,
  }
  patch = patch_header + '\n'.join(diff)
  patch = patch.rstrip() + '\n'
  return (patch, base_checksum, base_hashes)


def PerformBisect(bisect_job):
  """Performs the bisect on the try bot.

  This creates a patch, uploads it, then tells Rietveld to try the patch.

  TODO(qyearsley): If we want to use other tryservers sometimes in the future,
  then we need to have some way to decide which one to use. This could
  perhaps be passed as part of the bisect bot name, or guessed from the bisect
  bot name.

  Args:
    bisect_job: TryJob entity with initialized bot name and config.

  Returns:
    A dictionary containing the result; if successful, this dictionary contains
    the field "issue_id", otherwise it contains "error".
  """
  assert bisect_job.bot and bisect_job.config

  if bisect_job.use_buildbucket:
    return PerformBuildbucketBisect(bisect_job)

  config = bisect_job.config
  bot = bisect_job.bot
  email = bisect_job.email
  bug_id = bisect_job.bug_id

  # Get the base config file contents and make a patch.
  base_config = update_test_metadata.DownloadChromiumFile(_BISECT_CONFIG_PATH)
  if not base_config:
    return {'error': 'Error downloading base config'}
  patch, base_checksum, base_hashes = _CreatePatch(
      base_config, config, _BISECT_CONFIG_PATH)

  # Check if bisect is for internal only tests.
  bisect_internal = False

  # Upload the patch to Rietveld.
  server = rietveld_service.RietveldService(bisect_internal)

  subject = 'Perf bisect for bug %s on behalf of %s' % (bug_id, email)
  issue_id, patchset_id = server.UploadPatch(subject,
                                             patch,
                                             base_checksum,
                                             base_hashes,
                                             base_config,
                                             _BISECT_CONFIG_PATH)

  if not issue_id:
    return {'error': 'Error uploading patch to rietveld_service.'}

  if bisect_internal:
    # Internal server URL has '/bots', that cannot be accessed via browser,
    # therefore strip this path from internal server URL.
    issue_url = '%s/%s' % (server.Config().internal_server_url.strip('/bots'),
                           issue_id)
  else:
    issue_url = '%s/%s' % (server.Config().server_url.strip('/bots'), issue_id)

  # Tell Rietveld to try the patch.
  master = 'tryserver.chromium.perf'
  trypatch_success = server.TryPatch(master, issue_id, patchset_id, bot)
  if trypatch_success:
    # Create TryJob entity.  update_bug_from_rietveld and auto_bisect
    # cron job will be tracking/starting/restarting bisect.
    if bug_id and bug_id > 0:
      bisect_job.rietveld_issue_id = int(issue_id)
      bisect_job.rietveld_patchset_id = int(patchset_id)
      bisect_job.SetStarted()
      bug_comment = ('Bisect started; track progress at <a href="%s">%s</a>'
                     % (issue_url, issue_url))
      LogBisectResult(bug_id, bug_comment)
    return {'issue_id': issue_id, 'issue_url': issue_url}
  return {'error': 'Error starting try job. Try to fix at %s' % issue_url}


def _PerformPerfTryJob(perf_job):
  """Performs the perf try job on the try bot.

  This creates a patch, uploads it, then tells Rietveld to try the patch.

  Args:
    perf_job: TryJob entity with initialized bot name and config.

  Returns:
    A dictionary containing the result; if successful, this dictionary contains
    the field "issue_id", otherwise it contains "error".
  """
  assert perf_job.bot and perf_job.config
  config = perf_job.config
  bot = perf_job.bot
  email = perf_job.email

  # Get the base config file contents and make a patch.
  base_config = update_test_metadata.DownloadChromiumFile(_PERF_CONFIG_PATH)
  if not base_config:
    return {'error': 'Error downloading base config'}
  patch, base_checksum, base_hashes = _CreatePatch(
      base_config, config, _PERF_CONFIG_PATH)

  # Upload the patch to Rietveld.
  server = rietveld_service.RietveldService()
  subject = 'Perf Try Job on behalf of %s' % email
  issue_id, patchset_id = server.UploadPatch(subject,
                                             patch,
                                             base_checksum,
                                             base_hashes,
                                             base_config,
                                             _PERF_CONFIG_PATH)

  if not issue_id:
    return {'error': 'Error uploading patch to rietveld_service.'}
  url = 'https://codereview.chromium.org/%s/' % issue_id

  # Tell Rietveld to try the patch.
  master = 'tryserver.chromium.perf'
  trypatch_success = server.TryPatch(master, issue_id, patchset_id, bot)
  if trypatch_success:
    # Create TryJob entity. The update_bug_from_rietveld and auto_bisect
    # cron jobs will be tracking, or restarting the job.
    perf_job.rietveld_issue_id = int(issue_id)
    perf_job.rietveld_patchset_id = int(patchset_id)
    perf_job.SetStarted()
    return {'issue_id': issue_id}
  return {'error': 'Error starting try job. Try to fix at %s' % url}


def CheckBisectability(good_revision, bad_revision, test_path=None, bot=None):
  """Whether a bisect can be done for the given testpath, bot and revision.

  Checks for following conditions:
  1. Given revisions are integer.
  2. Non-bisectable revisions for android bots (refer to crbug.com/385324).
  3. Non-bisectable revisions for Windows bots (refer to crbug.com/405274).
  4. Non-bisectable test suites.

  Args:
    good_revision: Known good revision.
    bad_revision: known bad revision.
    test_path: A string test path.
    bot: Name of the bisect bot.

  Returns:
    None if bisectable, otherwise a dictionary with key "error" and the reason
    why.
  """
  # Checks whether the input is SHA1 hash or 5 to 7 digit number.
  for revision in [good_revision, bad_revision]:
    if (not re.match(r'^[a-fA-F0-9]{40}$', str(revision)) and
        not re.match(r'^[\d]{5,7}$', str(revision))):
      return {'error': 'Not a Chromium revision.'}

  if bot and 'android' in bot and good_revision < 265549:
    return {'error': ('Oops! Cannot bisect the given revision range.'
                      'It is impossible to bisect Android regressions prior '
                      'to r265549, which allows the bisect bot to rely on '
                      'Telemetry to do apk installation of the most recently '
                      'built local ChromeShell (refer to crbug.com/385324). '
                      'Please try bisecting revisions greater than or '
                      'equal to r265549.')}

  if (bot and 'win' in bot and
      (289987 <= good_revision < 290716 or 289987 <= bad_revision < 290716)):
    return {'error': ('Oops! Revision between r289987 and r290716 are marked '
                      'as dead zone for Windows due to crbug.com/405274.'
                      'Please try another range.')}
  if test_path:
    test_path_parts = test_path.split('/')
    if len(test_path_parts) < 4:
      return {'error': 'Invalid test path.'}

    if test_path_parts[2] in _UNBISECTABLE_SUITES:
      return {'error': 'Unbisectable test suite.'}

    # Check whether the given test path is for a reference build.
    if test_path.endswith('/ref') or test_path.endswith('_ref'):
      return {'error': 'Test path is for a reference build.'}

  return None


def LogBisectResult(bug_id, comment):
  """Adds bisect results to log.

  Args:
    bug_id: ID of the issue.
    comment: Bisect results information.
  """
  if not bug_id or bug_id < 0:
    return
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('bisect_result', bug_id, formatter)
  logger.Log(comment)
  logger.Save()


def _MakeBuildbucketBisectJob(bisect_job):
  """Creates a bisect job object that the buildbucket service can use.

  Args:
    bisect_job: The entity (try_job.TryJob) off of which to create the
        buildbucket job.

  Returns:
    A buildbucket_job.BisectJob object populated with the necessary attributes
    to pass it to the buildbucket service to start the job.
  """
  config = bisect_job.GetConfigDict()
  if not bisect_job.bot.startswith('linux'):
    raise request_handler.InvalidInputError(
        'Only linux is supported at this time.')
  if bisect_job.job_type != 'bisect':
    raise request_handler.InvalidInputError(
        'Recipe only supports bisect jobs at this time.')
  if bisect_job.master_name != 'ChromiumPerf':
    raise request_handler.InvalidInputError(
        'Recipe is only implemented on ChromiumPerf.')
  return buildbucket_job.BisectJob(
      platform='linux',
      good_revision=config['good_revision'],
      bad_revision=config['bad_revision'],
      test_command=config['command'],
      metric=config['metric'],
      repeats=config['repeat_count'],
      timeout_minutes=config['max_time_minutes'],
      truncate=config['truncate_percent'],
      bug_id=bisect_job.bug_id,
      gs_bucket='chrome-perf')


def PerformBuildbucketBisect(bisect_job):
  try:
    bisect_job.buildbucket_job_id = buildbucket_service.PutJob(
        _MakeBuildbucketBisectJob(bisect_job))
    bisect_job.SetStarted()
    return {
        'issue_id': bisect_job.buildbucket_job_id,
        'issue_url': '/buildbucket_job_status/' + bisect_job.buildbucket_job_id,
    }
  except httplib2.HttpLib2Error as e:
    return {
        'error': ('Could not start job because of the following exception: ' +
                  e.message),
    }
