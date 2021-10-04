# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import shlex

from dashboard.api import api_request_handler
from dashboard.common import bot_configurations
from dashboard.common import utils
from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models import quest as quest_module
from dashboard.pinpoint.models import scheduler
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models.tasks import performance_bisection
from dashboard.pinpoint.models.tasks import read_value

_ERROR_BUG_ID = 'Bug ID must be an integer.'
_ERROR_TAGS_DICT = 'Tags must be a dict of key/value string pairs.'
_ERROR_UNSUPPORTED = 'This benchmark (%s) is unsupported.'
_ERROR_PRIORITY = 'Priority must be an integer.'

REGULAR_TELEMETRY_TESTS = {
    'performance_weblayer_test_suite',
    'performance_webview_test_suite',
}
SUFFIXED_REGULAR_TELEMETRY_TESTS = {
    'performance_test_suite',
    'telemetry_perf_tests',
}
SUFFIXES = {
    '',
    '_android_chrome',
    '_android_monochrome',
    '_android_monochrome_bundle',
    '_android_weblayer',
    '_android_webview',
    '_android_clank_chrome',
    '_android_clank_monochrome',
    '_android_clank_monochrome_64_32_bundle',
    '_android_clank_monochrome_bundle',
    '_android_clank_trichrome_bundle',
    '_android_clank_trichrome_webview',
    '_android_clank_trichrome_webview_bundle',
    '_android_clank_webview',
    '_android_clank_webview_bundle',
}
# Map from target to fallback target.
REGULAR_TELEMETRY_TESTS_WITH_FALLBACKS = {}
for test in SUFFIXED_REGULAR_TELEMETRY_TESTS:
  for suffix in SUFFIXES:
    REGULAR_TELEMETRY_TESTS_WITH_FALLBACKS[test + suffix] = test


class New(api_request_handler.ApiRequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def _CheckUser(self):
    self._CheckIsLoggedIn()
    if not utils.IsTryjobUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    # TODO(dberris): Validate the inputs based on the type of job requested.
    job = _CreateJob(self.request)

    # We apply the cost-based scheduling at job creation time, so that we can
    # roll out the feature as jobs come along.
    scheduler.Schedule(job, scheduler.Cost(job))

    job.PostCreationUpdate()

    return {
        'jobId': job.job_id,
        'jobUrl': job.url,
    }


def _CreateJob(request):
  """Creates a new Pinpoint job from WebOb request arguments."""
  original_arguments = request.params.mixed()
  logging.debug('Received Params: %s', original_arguments)

  # This call will fail if some of the required arguments are not in the
  # original request.
  _ValidateRequiredParams(original_arguments)

  arguments = _ArgumentsWithConfiguration(original_arguments)
  logging.debug('Updated Params: %s', arguments)

  # Validate arguments and convert them to canonical internal representation.
  quests = _GenerateQuests(arguments)

  # Validate the priority, if it's present.
  priority = _ValidatePriority(arguments.get('priority'))

  # Validate and find the associated issue.
  bug_id, project = _ValidateBugId(
      arguments.get('bug_id'), arguments.get('project', 'chromium'))
  comparison_mode = _ValidateComparisonMode(arguments.get('comparison_mode'))
  comparison_magnitude = _ValidateComparisonMagnitude(
      arguments.get('comparison_magnitude'))
  gerrit_server, gerrit_change_id = _ValidatePatch(
      arguments.get('patch', arguments.get('experiment_patch')))
  name = arguments.get('name')
  pin = _ValidatePin(arguments.get('pin'))
  tags = _ValidateTags(arguments.get('tags'))
  user = _ValidateUser(arguments.get('user'))
  changes = _ValidateChanges(comparison_mode, arguments)

  # If this is a try job, we assume it's higher priority than bisections, so
  # we'll set it at a negative priority.
  if priority not in arguments and comparison_mode == job_state.TRY:
    priority = -1

  # TODO(dberris): Make this the default when we've graduated the beta.
  use_execution_engine = (
      arguments.get('experimental_execution_engine')
      and arguments.get('comparison_mode') == job_state.PERFORMANCE)

  # Ensure that we have the required fields in tryjob requests.
  if comparison_mode == 'try':
    if 'benchmark' not in arguments:
      raise ValueError('Missing required "benchmark" argument.')

    # First we check whether there's a quest that's of type 'RunTelemetryTest'.
    is_telemetry_test = any(
        [isinstance(q, quest_module.RunTelemetryTest) for q in quests])
    if is_telemetry_test and ('story' not in arguments
                              and 'story_tags' not in arguments):
      raise ValueError(
          'Missing either "story" or "story_tags" as arguments for try jobs.')

  # Create job.
  job = job_module.Job.New(
      quests if not use_execution_engine else (),
      changes,
      arguments=original_arguments,
      bug_id=bug_id,
      comparison_mode=comparison_mode,
      comparison_magnitude=comparison_magnitude,
      gerrit_server=gerrit_server,
      gerrit_change_id=gerrit_change_id,
      name=name,
      pin=pin,
      tags=tags,
      user=user,
      priority=priority,
      use_execution_engine=use_execution_engine,
      project=project,
      batch_id=arguments.get('batch_id'))

  if use_execution_engine:
    # TODO(dberris): We need to figure out a way to get the arguments to be more
    # structured when it comes in from the UI, so that we don't need to do the
    # manual translation of options here.
    # TODO(dberris): Decide whether we can make some of these hard-coded options
    # be part of a template that's available in the UI (or by configuration
    # somewhere else, maybe luci-config?)
    start_change, end_change = changes
    target = arguments.get('target')
    task_options = performance_bisection.TaskOptions(
        build_option_template=performance_bisection.BuildOptionTemplate(
            builder=arguments.get('builder'),
            target=target,
            bucket=arguments.get('bucket', 'master.tryserver.chromium.perf'),
        ),
        test_option_template=performance_bisection.TestOptionTemplate(
            swarming_server=arguments.get('swarming_server'),
            dimensions=arguments.get('dimensions'),
            extra_args=arguments.get('extra_test_args'),
        ),
        read_option_template=performance_bisection.ReadOptionTemplate(
            benchmark=arguments.get('benchmark'),
            histogram_options=read_value.HistogramOptions(
                grouping_label=arguments.get('grouping_label'),
                story=arguments.get('story'),
                statistic=arguments.get('statistic'),
                histogram_name=arguments.get('chart'),
            ),
            graph_json_options=read_value.GraphJsonOptions(
                chart=arguments.get('chart'), trace=arguments.get('trace')),
            mode=('histogram_sets'
                  if target in performance_bisection.EXPERIMENTAL_TARGET_SUPPORT
                  else 'graph_json')),
        analysis_options=performance_bisection.AnalysisOptions(
            comparison_magnitude=arguments.get('comparison_magnitude'),
            min_attempts=10,
            max_attempts=60,
        ),
        start_change=start_change,
        end_change=end_change,
        pinned_change=arguments.get('patch'),
    )
    task_module.PopulateTaskGraph(
        job, performance_bisection.CreateGraph(task_options, arguments))
  return job


def _ParseExtraArgs(args):
  extra_args = []
  if args:
    try:
      extra_args = json.loads(args)
    except ValueError:
      extra_args = shlex.split(args)
  return extra_args


def _ArgumentsWithConfiguration(original_arguments):
  # "configuration" is a special argument that maps to a list of preset
  # arguments. Pull any arguments from the specified "configuration", if any.
  new_arguments = original_arguments.copy()

  configuration = original_arguments.get('configuration')
  if configuration:
    try:
      default_arguments = bot_configurations.Get(configuration)
    except ValueError:
      # Reraise with a clearer message.
      raise ValueError("Bot Config: %s doesn't exist." % configuration)
    logging.info('Bot Config: %s', default_arguments)

    if default_arguments:
      for k, v in list(default_arguments.items()):
        # We special-case the extra_test_args argument to be additive, so that
        # we can respect the value set in bot_configurations in addition to
        # those provided from the UI.
        if k == 'extra_test_args':
          # First, parse whatever is already there. We'll canonicalise the
          # inputs as a JSON list of strings.
          provided_args = new_arguments.get('extra_test_args', '')
          extra_test_args = []

          if provided_args:
            extra_test_args = _ParseExtraArgs(provided_args)

          configured_args = _ParseExtraArgs(v)
          new_arguments['extra_test_args'] = json.dumps(
              extra_test_args + configured_args,)
        else:
          new_arguments.setdefault(k, v)

  return new_arguments


def _ValidateBugId(bug_id, project):
  if not bug_id:
    return None, None

  try:
    # TODO(dberris): Figure out a way to check the issue tracker if the project
    # is valid at creation time. That might involve a user credential check, so
    # we might need to update the scopes we're asking for. For now trust that
    # the inputs are valid.
    return int(bug_id), project
  except ValueError:
    raise ValueError(_ERROR_BUG_ID)


def _ValidatePriority(priority):
  if not priority:
    return None

  try:
    return int(priority)
  except ValueError:
    raise ValueError(_ERROR_PRIORITY)


def _ValidateChangesForTry(arguments):
  if 'base_git_hash' not in arguments:
    raise ValueError('base_git_hash is required for try jobs')

  commit_1 = change.Commit.FromDict({
      'repository': arguments.get('repository'),
      'git_hash': arguments.get('base_git_hash'),
  })
  commit_2 = change.Commit.FromDict({
      'repository':
          arguments.get('repository'),
      'git_hash':
          arguments.get(
              'end_git_hash',
              arguments.get(
                  'experiment_git_hash',
                  arguments.get('base_git_hash'),
              ),
          ),
  })

  # Now, if we have a patch argument, we need to handle the case where a patch
  # needs to be applied to both the 'end_git_hash' and the 'base_git_hash'.
  patch = arguments.get('patch')
  if patch:
    patch = change.GerritPatch.FromUrl(patch)

  exp_patch = arguments.get('experiment_patch')
  if exp_patch:
    exp_patch = change.GerritPatch.FromUrl(exp_patch)

  base_patch = arguments.get('base_patch')
  if base_patch:
    base_patch = change.GerritPatch.FromUrl(base_patch)

  if commit_1.git_hash != commit_2.git_hash and patch:
    base_patch = patch
    exp_patch = patch

  if not exp_patch:
    exp_patch = patch

  base_extra_args = _ParseExtraArgs(arguments.get('base_extra_args', ''))
  logging.debug('Base extra args: %s', base_extra_args)
  change_1 = change.Change(
      commits=(commit_1,),
      patch=base_patch,
      label='base',
      args=base_extra_args or None,
      variant=0)
  exp_extra_args = _ParseExtraArgs(arguments.get('experiment_extra_args', ''))
  logging.debug('Experiment extra args: %s', exp_extra_args)
  change_2 = change.Change(
      commits=(commit_2,),
      patch=exp_patch,
      label='exp',
      args=exp_extra_args or None,
      variant=1)
  return change_1, change_2


def _ValidateChanges(comparison_mode, arguments):
  try:
    changes = arguments.get('changes')
    if changes:
      # FromData() performs input validation.
      return [change.Change.FromData(c) for c in json.loads(changes)]

    # There are valid cases where a tryjob requests a base_git_hash and an
    # end_git_hash without a patch. Let's check first whether we're finding the
    # right combination of inputs here.
    if comparison_mode == job_state.TRY:
      return _ValidateChangesForTry(arguments)

    # Everything else that follows only applies to bisections.
    assert (comparison_mode == job_state.FUNCTIONAL
            or comparison_mode == job_state.PERFORMANCE)

    if 'start_git_hash' not in arguments or 'end_git_hash' not in arguments:
      raise ValueError(
          'bisections require both a start_git_hash and an end_git_hash')

    commit_1 = change.Commit.FromDict({
        'repository': arguments.get('repository'),
        'git_hash': arguments.get('start_git_hash'),
    })

    commit_2 = change.Commit.FromDict({
        'repository': arguments.get('repository'),
        'git_hash': arguments.get('end_git_hash'),
    })

    if 'patch' in arguments:
      patch = change.GerritPatch.FromUrl(arguments['patch'])
    else:
      patch = None

    # If we find a patch in the request, this means we want to apply it even to
    # the start commit.
    change_1 = change.Change(commits=(commit_1,), patch=patch)
    change_2 = change.Change(commits=(commit_2,), patch=patch)

    return change_1, change_2
  except errors.BuildGerritURLInvalid as e:
    raise ValueError(str(e))


def _ValidatePatch(patch_data):
  if patch_data:
    try:
      patch_details = change.GerritPatch.FromData(patch_data)
    except errors.BuildGerritURLInvalid as e:
      raise ValueError(str(e))
    return patch_details.server, patch_details.change
  return None, None


def _ValidateComparisonMode(comparison_mode):
  if not comparison_mode:
    comparison_mode = job_state.TRY
  if comparison_mode and comparison_mode not in job_module.COMPARISON_MODES:
    raise ValueError('`comparison_mode` should be one of %s. Got "%s".' %
                     (job_module.COMPARISON_MODES + (None,), comparison_mode))
  return comparison_mode


def _ValidateComparisonMagnitude(comparison_magnitude):
  if not comparison_magnitude:
    return 1.0
  return float(comparison_magnitude)


def _GenerateQuests(arguments):
  """Generate a list of Quests from a dict of arguments.

  GenerateQuests uses the arguments to infer what types of Quests the user wants
  to run, and creates a list of Quests with the given configuration.

  Arguments:
    arguments: A dict or MultiDict containing arguments.

  Returns:
    A tuple of (arguments, quests), where arguments is a dict containing the
    request arguments that were used, and quests is a list of Quests.
  """
  quests = arguments.get('quests')
  if quests:
    if isinstance(quests, basestring):
      quests = quests.split(',')
    quest_classes = []
    for quest in quests:
      if not hasattr(quest_module, quest):
        raise ValueError('Unknown quest: "%s"' % quest)
      quest_classes.append(getattr(quest_module, quest))
  else:
    target = arguments.get('target')
    logging.debug('Target: %s', target)

    if target in REGULAR_TELEMETRY_TESTS:
      quest_classes = (quest_module.FindIsolate, quest_module.RunTelemetryTest,
                       quest_module.ReadValue)
    elif target in REGULAR_TELEMETRY_TESTS_WITH_FALLBACKS:
      if 'fallback_target' not in arguments:
        fallback_target = REGULAR_TELEMETRY_TESTS_WITH_FALLBACKS[target]
        logging.debug('Adding "fallback_target" to params with value %s',
                      fallback_target)
        arguments['fallback_target'] = fallback_target
      quest_classes = (quest_module.FindIsolate, quest_module.RunTelemetryTest,
                       quest_module.ReadValue)
    elif 'performance_test_suite_eve' in target:
      quest_classes = (quest_module.FindIsolate,
                       quest_module.RunLacrosTelemetryTest,
                       quest_module.ReadValue)
    elif 'performance_web_engine_test_suite' in target:
      quest_classes = (quest_module.FindIsolate,
                       quest_module.RunWebEngineTelemetryTest,
                       quest_module.ReadValue)
    elif target == 'vr_perf_tests':
      quest_classes = (quest_module.FindIsolate,
                       quest_module.RunVrTelemetryTest, quest_module.ReadValue)
    elif 'browser_test' in target:
      quest_classes = (quest_module.FindIsolate, quest_module.RunBrowserTest,
                       quest_module.ReadValue)
    elif 'instrumentation_test' in target:
      quest_classes = (quest_module.FindIsolate,
                       quest_module.RunInstrumentationTest,
                       quest_module.ReadValue)
    elif 'webrtc_perf_tests' in target:
      quest_classes = (quest_module.FindIsolate, quest_module.RunWebRtcTest,
                       quest_module.ReadValue)
    else:
      quest_classes = (quest_module.FindIsolate, quest_module.RunGTest,
                       quest_module.ReadValue)

  quest_instances = []
  for quest_class in quest_classes:
    # FromDict() performs input validation.
    quest_instances.append(quest_class.FromDict(arguments))

  return quest_instances


def _ValidatePin(pin):
  if not pin:
    return None
  return change.Change.FromData(pin)


def _ValidateTags(tags):
  if not tags:
    return {}

  tags_dict = json.loads(tags)

  if not isinstance(tags_dict, dict):
    raise ValueError(_ERROR_TAGS_DICT)

  for k, v in tags_dict.items():
    if not isinstance(k, basestring) or not isinstance(v, basestring):
      raise ValueError(_ERROR_TAGS_DICT)

  return tags_dict


def _ValidateUser(user):
  return user or utils.GetEmail()


_REQUIRED_NON_EMPTY_PARAMS = {'target', 'benchmark'}


def _ValidateRequiredParams(params):
  missing = _REQUIRED_NON_EMPTY_PARAMS - set(params.keys())
  if missing:
    raise ValueError('Missing required parameters: %s' % (list(missing)))
  # Check that they're not empty.
  empty_keys = [key for key in _REQUIRED_NON_EMPTY_PARAMS if not params[key]]
  if empty_keys:
    raise ValueError('Parameters must not be empty: %s' % (empty_keys))
