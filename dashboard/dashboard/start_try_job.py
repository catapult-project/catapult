# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint containing server-side functionality for bisect try jobs."""

import difflib
import hashlib
import json
import logging
import re

import httplib2

from google.appengine.api import users
from google.appengine.api import app_identity

from dashboard import buildbucket_job
from dashboard import buildbucket_service
from dashboard import namespaced_stored_object
from dashboard import quick_logger
from dashboard import request_handler
from dashboard import rietveld_service
from dashboard import stored_object
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

_BISECT_BOT_MAP_KEY = 'bisect_bot_map'
_BUILDER_TYPES_KEY = 'bisect_builder_types'
_TESTER_DIRECTOR_MAP_KEY = 'recipe_tester_director_map'

_NON_TELEMETRY_TEST_COMMANDS = {
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


class StartBisectHandler(request_handler.RequestHandler):
  """URL endpoint for AJAX requests for bisect config handling.

  Requests are made to this end-point by bisect and trace forms. This handler
  does several different types of things depending on what is given as the
  value of the "step" parameter:
    "prefill-info": Returns JSON with some info to fill into the form.
    "perform-bisect": Triggers a bisect job.
    "perform-perf-try": Triggers a perf try job.
  """

  def post(self):
    """Performs one of several bisect-related actions depending on parameters.

    The only required parameter is "step", which indicates what to do.

    This end-point should always output valid JSON with different contents
    depending on the value of "step".
    """
    user = users.get_current_user()
    if not utils.IsValidSheriffUser():
      message = 'User "%s" not authorized.' % user
      self.response.out.write(json.dumps({'error': message}))
      return

    step = self.request.get('step')

    if step == 'prefill-info':
      result = _PrefillInfo(self.request.get('test_path'))
    elif step == 'perform-bisect':
      result = self._PerformBisectStep(user)
    elif step == 'perform-perf-try':
      result = self._PerformPerfTryStep(user)
    else:
      result = {'error': 'Invalid parameters.'}

    self.response.write(json.dumps(result))

  def _PerformBisectStep(self, user):
    """Gathers the parameters for a bisect job and triggers the job."""
    bug_id = int(self.request.get('bug_id', -1))
    master_name = self.request.get('master', 'ChromiumPerf')
    internal_only = self.request.get('internal_only') == 'true'
    bisect_bot = self.request.get('bisect_bot')
    bypass_no_repro_check = self.request.get('bypass_no_repro_check') == 'true'
    use_recipe = bool(GetBisectDirectorForTester(bisect_bot))

    bisect_config = GetBisectConfig(
        bisect_bot=bisect_bot,
        master_name=master_name,
        suite=self.request.get('suite'),
        metric=self.request.get('metric'),
        good_revision=self.request.get('good_revision'),
        bad_revision=self.request.get('bad_revision'),
        repeat_count=self.request.get('repeat_count', 10),
        max_time_minutes=self.request.get('max_time_minutes', 20),
        truncate_percent=self.request.get('truncate_percent', 25),
        bug_id=bug_id,
        use_archive=self.request.get('use_archive'),
        bisect_mode=self.request.get('bisect_mode', 'mean'),
        use_buildbucket=use_recipe,
        bypass_no_repro_check=bypass_no_repro_check)

    if 'error' in bisect_config:
      return bisect_config

    config_python_string = 'config = %s\n' % json.dumps(
        bisect_config, sort_keys=True, indent=2, separators=(',', ': '))

    bisect_job = try_job.TryJob(
        bot=bisect_bot,
        config=config_python_string,
        bug_id=bug_id,
        email=user.email(),
        master_name=master_name,
        internal_only=internal_only,
        job_type='bisect',
        use_buildbucket=use_recipe)

    try:
      result = PerformBisect(bisect_job)
    except request_handler.InvalidInputError as iie:
      result = {'error': iie.message}
    return result

  def _PerformPerfTryStep(self, user):
    """Gathers the parameters required for a perf try job and starts the job."""
    perf_config = _GetPerfTryConfig(
        bisect_bot=self.request.get('bisect_bot'),
        suite=self.request.get('suite'),
        good_revision=self.request.get('good_revision'),
        bad_revision=self.request.get('bad_revision'),
        rerun_option=self.request.get('rerun_option'))

    if 'error' in perf_config:
      return perf_config

    config_python_string = 'config = %s\n' % json.dumps(
        perf_config, sort_keys=True, indent=2, separators=(',', ': '))

    perf_job = try_job.TryJob(
        bot=self.request.get('bisect_bot'),
        config=config_python_string,
        bug_id=-1,
        email=user.email(),
        job_type='perf-try')

    return _PerformPerfTryJob(perf_job)


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

  info['all_bots'] = _GetAvailableBisectBots(suite.master_name)
  info['bisect_bot'] = GuessBisectBot(suite.master_name, suite.bot_name)

  user = users.get_current_user()
  if not user:
    return {'error': 'User not logged in.'}

  # Secondary check for bisecting internal only tests.
  if suite.internal_only and not utils.IsInternalUser():
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


def GetBisectConfig(
    bisect_bot, master_name, suite, metric, good_revision, bad_revision,
    repeat_count, max_time_minutes, truncate_percent, bug_id, use_archive=None,
    bisect_mode='mean', use_buildbucket=False, bypass_no_repro_check=False):
  """Fills in a JSON response with the filled-in config file.

  Args:
    bisect_bot: Bisect bot name. (This should be either a legacy bisector or a
        recipe-enabled tester).
    master_name: Master name of the test being bisected.
    suite: Test suite name of the test being bisected.
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
    use_buildbucket: Whether this job will started using buildbucket,
        this should be used for bisects using the bisect recipe.

  Returns:
    A dictionary with the result; if successful, this will contain "config",
    which is a config string; if there's an error, this will contain "error".
  """
  command = GuessCommand(
      bisect_bot, suite, metric=metric, use_buildbucket=use_buildbucket)
  if not command:
    return {'error': 'Could not guess command for %r.' % suite}

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

  if not IsValidRevisionForBisect(good_revision):
    return {'error': 'Invalid "good" revision "%s".' % good_revision}
  if not IsValidRevisionForBisect(bad_revision):
    return {'error': 'Invalid "bad" revision "%s".' % bad_revision}

  config_dict = {
      'command': command,
      'good_revision': str(good_revision),
      'bad_revision': str(bad_revision),
      'metric': metric,
      'repeat_count': str(repeat_count),
      'max_time_minutes': str(max_time_minutes),
      'truncate_percent': str(truncate_percent),
      'bug_id': str(bug_id),
      'builder_type': _BuilderType(master_name, use_archive),
      'target_arch': GuessTargetArch(bisect_bot),
      'bisect_mode': bisect_mode,
  }
  if use_buildbucket:
    config_dict['recipe_tester_name'] = bisect_bot
  if bypass_no_repro_check:
    config_dict['required_initial_confidence'] = '0'
  return config_dict


def _BuilderType(master_name, use_archive):
  """Returns the builder_type string to use in the bisect config.

  Args:
    master_name: The test master name.
    use_archive: Whether or not to use archived builds.

  Returns:
    A string which indicates where the builds should be obtained from.
  """
  if not use_archive:
    return ''
  builder_types = namespaced_stored_object.Get(_BUILDER_TYPES_KEY)
  if not builder_types or master_name not in builder_types:
    return 'perf'
  return builder_types[master_name]


def GuessTargetArch(bisect_bot):
  """Return target architecture for the bisect job."""
  if 'x64' in bisect_bot or 'win64' in bisect_bot:
    return 'x64'
  elif bisect_bot in ['android_nexus9_perf_bisect']:
    return 'arm64'
  else:
    return 'ia32'


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
    return {'error': 'Only Telemetry is supported at the moment.'}

  if not IsValidRevisionForBisect(good_revision):
    return {'error': 'Invalid "good" revision "%s".' % good_revision}
  if not IsValidRevisionForBisect(bad_revision):
    return {'error': 'Invalid "bad" revision "%s".' % bad_revision}

  config_dict = {
      'command': command,
      'good_revision': str(good_revision),
      'bad_revision': str(bad_revision),
      'repeat_count': '1',
      'max_time_minutes': '60',
      'truncate_percent': '0',
  }
  return config_dict


def IsValidRevisionForBisect(revision):
  """Checks whether a revision looks like a valid revision for bisect."""
  return _IsGitHash(revision) or re.match(r'^[0-9]{5,7}$', str(revision))


def _IsGitHash(revision):
  """Checks whether the input looks like a SHA1 hash."""
  return re.match(r'[a-fA-F0-9]{40}$', str(revision))


def _GetAvailableBisectBots(master_name):
  """Get all available bisect bots corresponding to a master name."""
  bisect_bot_map = namespaced_stored_object.Get(_BISECT_BOT_MAP_KEY)
  for master, platform_bot_pairs in bisect_bot_map.iteritems():
    if master_name.startswith(master):
      return sorted({bot for _, bot in platform_bot_pairs})
  return []


def _CanDownloadBuilds(master_name):
  """Check whether bisecting using archives is supported."""
  return master_name.startswith('ChromiumPerf')


def GuessBisectBot(master_name, bot_name):
  """Returns a bisect bot name based on |bot_name| (perf_id) string."""
  fallback = 'linux_perf_bisect'
  bisect_bot_map = namespaced_stored_object.Get(_BISECT_BOT_MAP_KEY)
  if not bisect_bot_map:
    return fallback
  bot_name = bot_name.lower()
  for master, platform_bot_pairs in bisect_bot_map.iteritems():
    # Treat ChromiumPerfFyi (etc.) the same as ChromiumPerf.
    if master_name.startswith(master):
      for platform, bisect_bot in platform_bot_pairs:
        if platform in bot_name:
          return bisect_bot
  # Nothing was found; log a warning and return a fall-back name.
  logging.warning('No bisect bot for %s/%s.', master_name, bot_name)
  return fallback


def GuessCommand(
    bisect_bot, suite, metric=None, rerun_option=None, use_buildbucket=False):
  """Returns a command to use in the bisect configuration."""
  if suite in _NON_TELEMETRY_TEST_COMMANDS:
    return _GuessCommandNonTelemetry(suite, bisect_bot, use_buildbucket)
  return _GuessCommandTelemetry(
      suite, bisect_bot, metric, rerun_option, use_buildbucket)


def _GuessCommandNonTelemetry(suite, bisect_bot, use_buildbucket):
  """Returns a command string to use for non-Telemetry tests."""
  if suite not in _NON_TELEMETRY_TEST_COMMANDS:
    return None
  if suite == 'cc_perftests' and bisect_bot.startswith('android'):
    if use_buildbucket:
      return 'src/build/android/test_runner.py gtest --release -s cc_perftests'
    else:
      return 'build/android/test_runner.py gtest --release -s cc_perftests'

  command = list(_NON_TELEMETRY_TEST_COMMANDS[suite])

  if use_buildbucket and command[0].startswith('./out'):
    command[0] = command[0].replace('./', './src/')

  if bisect_bot.startswith('win'):
    command[0] = command[0].replace('/', '\\')
    command[0] += '.exe'
  return ' '.join(command)


def _GuessCommandTelemetry(
    suite, bisect_bot, metric,  # pylint: disable=unused-argument
    rerun_option, use_buildbucket):
  """Returns a command to use given that |suite| is a Telemetry benchmark."""
  # TODO(qyearsley): Use metric to add a --story-filter flag for Telemetry.
  # See: http://crbug.com/448628
  command = []
  if bisect_bot.startswith('win'):
    command.append('python')

  if use_buildbucket:
    test_cmd = 'src/tools/perf/run_benchmark'
  else:
    test_cmd = 'tools/perf/run_benchmark'

  command.extend([
      test_cmd,
      '-v',
      '--browser=%s' % _GuessBrowserName(bisect_bot),
      '--output-format=%s' % ('chartjson' if use_buildbucket else 'buildbot'),
      '--also-run-disabled-tests',
  ])

  profile_dir = _GuessProfileDir(suite, use_buildbucket)
  if profile_dir:
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


def _GuessBrowserName(bisect_bot):
  """Returns a browser name string for Telemetry to use."""
  if bisect_bot.startswith('android'):
    return 'android-chromium'
  if bisect_bot.startswith('clankium'):
    return 'android-chrome'
  if bisect_bot.startswith('win') and 'x64' in bisect_bot:
    return 'release_x64'

  return 'release'


def _GuessProfileDir(suite, use_buildbucket):
  """Returns a profile directory string for Telemetry, or None."""
  if (suite == 'startup.warm.dirty.blank_page' or
      suite == 'startup.cold.dirty.blank_page' or
      suite.startswith('session_restore')):
    # Profile directory relative to build directory on slave.
    if use_buildbucket:
      return 'src/out/Release/generated_profile/small_profile'
    # Profile directory relative to chromium/src.
    else:
      return 'out/Release/generated_profile/small_profile'
  return None


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


def _RewriteMetricName(metric):
  """Rewrites a metric name for legacy bisect.

  With the introduction of test names with interaction record labels coming
  from Telemetry, it is necessary to rewrite names to the format described in
  goo.gl/CXGyxT so that they can be interpreted by legacy bisect. Recipe bisect
  does the rewriting itself.

  For instance, foo/bar/baz would be rewritten as bar-foo/baz.

  Args:
    metric: The slash-separated metric name, generally from GuessMetric.

  Returns:
    The Buildbot output format-compatible metric name.
  """
  test_parts = metric.split('/')

  if len(test_parts) == 3:
    chart_name, interaction_record_name, trace_name = test_parts
    return '%s-%s/%s' % (interaction_record_name,
                         chart_name,
                         trace_name)
  else:
    return metric


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
    the field "issue_id" and "issue_url", otherwise it contains "error".
  """
  assert bisect_job.bot and bisect_job.config

  if bisect_job.use_buildbucket:
    return PerformBuildbucketBisect(bisect_job)

  config = bisect_job.config
  bot = bisect_job.bot
  email = bisect_job.email
  bug_id = bisect_job.bug_id

  # We need to rewrite the metric name for legacy bisect.
  config_dict = bisect_job.GetConfigDict()
  config_dict['metric'] = _RewriteMetricName(config_dict['metric'])
  bisect_job.config = utils.BisectConfigPythonString(config_dict)

  # Get the base config file contents and make a patch.
  base_config = update_test_metadata.DownloadChromiumFile(_BISECT_CONFIG_PATH)
  if not base_config:
    return {'error': 'Error downloading base config'}
  patch, base_checksum, base_hashes = _CreatePatch(
      base_config, config, _BISECT_CONFIG_PATH)

  # Check if bisect is for internal only tests.
  bisect_internal = _IsBisectInternalOnly(bisect_job)

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
  master = _GetTryServerMaster(bisect_job)
  trypatch_success = server.TryPatch(master, issue_id, patchset_id, bot)
  if trypatch_success:
    # Create TryJob entity.  update_bug_with_results and auto_bisect
    # cron job will be tracking/starting/restarting bisect.
    if bug_id and bug_id > 0:
      bisect_job.rietveld_issue_id = int(issue_id)
      bisect_job.rietveld_patchset_id = int(patchset_id)
      bisect_job.SetStarted()
      bug_comment = ('Bisect started; track progress at '
                     '<a href="%s">%s</a>' % (issue_url, issue_url))
      LogBisectResult(bug_id, bug_comment)
    return {'issue_id': issue_id, 'issue_url': issue_url}
  return {'error': 'Error starting try job. Try to fix at %s' % issue_url}


def _IsBisectInternalOnly(bisect_job):
  """Checks if the bisect is for an internal-only test."""
  return (bisect_job.internal_only and
          bisect_job.master_name.startswith('Clank'))


def _GetTryServerMaster(bisect_job):
  """Returns the try server master to be used for bisecting."""
  if bisect_job.internal_only and bisect_job.master_name.startswith('Clank'):
    return 'tryserver.clankium'
  return 'tryserver.chromium.perf'


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
    # Create TryJob entity. The update_bug_with_results and auto_bisect
    # cron jobs will be tracking, or restarting the job.
    perf_job.rietveld_issue_id = int(issue_id)
    perf_job.rietveld_patchset_id = int(patchset_id)
    perf_job.SetStarted()
    return {'issue_id': issue_id}
  return {'error': 'Error starting try job. Try to fix at %s' % url}


def LogBisectResult(bug_id, comment):
  """Adds an entry to the bisect result log for a particular bug."""
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
  if bisect_job.job_type != 'bisect':
    raise request_handler.InvalidInputError(
        'Recipe only supports bisect jobs at this time.')
  if not bisect_job.master_name.startswith('ChromiumPerf'):
    raise request_handler.InvalidInputError(
        'Recipe is only implemented for tests run on chromium.perf '
        '(and chromium.perf.fyi).')

  # Recipe bisect supports 'perf' and 'return_code' test types only.
  # TODO (prasadv): Update bisect form on dashboard to support test_types.
  test_type = 'perf'
  if config.get('bisect_mode') == 'return_code':
    test_type = config['bisect_mode']

  return buildbucket_job.BisectJob(
      bisect_director=GetBisectDirectorForTester(config['recipe_tester_name']),
      good_revision=config['good_revision'],
      bad_revision=config['bad_revision'],
      test_command=config['command'],
      metric=config['metric'],
      repeats=config['repeat_count'],
      timeout_minutes=config['max_time_minutes'],
      truncate=config['truncate_percent'],
      bug_id=bisect_job.bug_id,
      gs_bucket='chrome-perf',
      recipe_tester_name=config['recipe_tester_name'],
      test_type=test_type,
      required_confidence=config.get('required_initial_confidence', '95')
  )


def PerformBuildbucketBisect(bisect_job):
  try:
    bisect_job.buildbucket_job_id = buildbucket_service.PutJob(
        _MakeBuildbucketBisectJob(bisect_job))
    bisect_job.SetStarted()
    hostname = app_identity.get_default_version_hostname()
    job_id = bisect_job.buildbucket_job_id
    issue_url = 'https://%s/buildbucket_job_status/%s' % (hostname, job_id)
    bug_comment = ('Bisect started; track progress at '
                   '<a href="%s">%s</a>' % (issue_url, issue_url))
    LogBisectResult(bisect_job.bug_id, bug_comment)
    return {
        'issue_id': job_id,
        'issue_url': issue_url,
    }
  except httplib2.HttpLib2Error as e:
    return {
        'error': ('Could not start job because of the following exception: ' +
                  e.message),
    }


def GetBisectDirectorForTester(bot):
  """Maps the name of a tester bot to its corresponding bisect director.

  Args:
    bot (str): The name of the tester bot in the tryserver.chromium.perf
        waterfall. (e.g. 'linux_perf_tester').

  Returns:
    The name of the bisect director that can use the given tester (e.g.
        'linux_perf_bisector')
  """
  recipe_tester_director_mapping = stored_object.Get(
      _TESTER_DIRECTOR_MAP_KEY)
  return recipe_tester_director_mapping.get(bot)
