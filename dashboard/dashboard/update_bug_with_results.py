# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to update bugs after bisects."""

import datetime
import json
import logging
import re
import sys
import urllib

from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.ext import ndb

from dashboard import buildbucket_service
from dashboard import email_template
from dashboard import issue_tracker_service
from dashboard import layered_cache
from dashboard import quick_logger
from dashboard import request_handler
from dashboard import rietveld_service
from dashboard import start_try_job
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models import try_job

# Try job status codes from rietveld (see TryJobResult in codereview/models.py)
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, TRYPENDING = range(7)
# Not a status code from rietveld, added for completeness of the possible
# statuses a job can be in.
STARTED = -1
OK = (SUCCESS, WARNINGS, SKIPPED)
FAIL = (FAILURE, EXCEPTION)

_COMMIT_HASH_CACHE_KEY = 'commit_hash_%s'

_CONFIDENCE_THRESHOLD = 99.5

# Timeout in minutes set by buildbot for trybots.
_BISECT_BOT_TIMEOUT = 12 * 60

# Amount of time to pass before deleting a try job.
_STALE_TRYJOB_DELTA = datetime.timedelta(days=7)

_BUG_COMMENT_TEMPLATE = """Bisect job status: %(status)s
Bisect job ran on: %(bisect_bot)s

%(results)s

Buildbot stdio: %(buildbot_log_url)s
Job details: %(issue_url)s
"""

_AUTO_ASSIGN_MSG = """
==== Auto-CCing suspected CL author %(author)s ====

Hi %(author)s, the bisect results pointed to your CL below as possibly
causing a regression. Please have a look at this info and see whether
your CL be related.

"""


class UnexpectedJsonError(Exception):
  pass


class BugUpdateFailure(Exception):
  pass


class UpdateBugWithResultsHandler(request_handler.RequestHandler):
  """URL endpoint for a cron job to update bugs after bisects."""

  def get(self):
    """The get handler method is called from a cron job.

    It expects no parameters and has no output. It checks all current bisect try
    jobs and send comments to an issue on the issue tracker if a bisect job has
    completed.
    """
    credentials = rietveld_service.Credentials(
        rietveld_service.GetDefaultRietveldConfig(),
        rietveld_service.PROJECTHOSTING_SCOPE)
    issue_tracker = issue_tracker_service.IssueTrackerService(
        additional_credentials=credentials)

    jobs_to_check = try_job.TryJob.query(
        try_job.TryJob.status == 'started').fetch()
    for job in jobs_to_check:
      try:
        if job.use_buildbucket:
          logging.info('Checking job %s with Buildbucket job ID %s.',
                       job.key.id(), getattr(job, 'buildbucket_job_id', None))
        else:
          logging.info('Checking job %s with Rietveld issue ID %s.',
                       job.key.id(), getattr(job, 'rietveld_issue_id', None))
        _CheckJob(job, issue_tracker)
      except Exception as e:  # pylint: disable=broad-except
        logging.error('Caught Exception %s: %s', type(e).__name__, e)


def _CheckJob(job, issue_tracker):
  """Checks whether a try job is finished and updates a bug if applicable.

  This method returns nothing, but it may log errors.

  Args:
    job: A TryJob entity, which represents one bisect try job.
    issue_tracker: An issue_tracker_service.IssueTrackerService instance.
  """
  # Give up on stale try job.
  if (job.last_ran_timestamp and
      job.last_ran_timestamp < datetime.datetime.now() - _STALE_TRYJOB_DELTA):
    comment = 'Stale bisect job cancelled.  Will retry again later.'
    comment += 'Rietveld issue: %s' % job.rietveld_issue_id
    start_try_job.LogBisectResult(job.bug_id, comment)
    job.SetFailed()
    return

  if job.job_type == 'perf-try':
    _CheckPerfTryJob(job)
  else:
    # Delete bisect jobs that aren't associated with any bug id.
    if job.bug_id is None or job.bug_id < 0:
      job.key.delete()
      return
    _CheckBisectJob(job, issue_tracker)


def _CheckPerfTryJob(job):
  perf_results = _GetPerfTryResults(job)
  if not perf_results:
    return
  _SendPerfTryJobEmail(job, perf_results)
  job.SetCompleted()


def _SendPerfTryJobEmail(job, perf_results):
  """Sends an email to the user who started the perf try job."""
  to = [job.email] if job.email else []
  if not to:
    logging.error('No "email" in job data. %s.', job.rietveld_issue_id)
    return

  perf_email = email_template.GetPerfTryJobEmail(perf_results)
  if not perf_email:
    logging.error('Failed to create "perf_email" from result data. %s.'
                  ' Results data: %s', job.rietveld_issue_id, perf_results)
    return

  mail.send_mail(sender='gasper-alerts@google.com',
                 to=','.join(to),
                 subject=perf_email['subject'],
                 body=perf_email['body'],
                 html=perf_email['html'])


def _ParseCloudLinksFromOutput(output):
  """Extracts cloud storage URLs from text."""
  html_results_pattern = re.compile(
      r'@@@STEP_LINK@HTML Results@(?P<link>http://storage.googleapis.com/'
      'chromium-telemetry/html-results/results-[a-z0-9-_]+)@@@',
      re.MULTILINE)
  profiler_pattern = re.compile(
      r'@@@STEP_LINK@(?P<title>[^@]+)@(?P<link>https://console.developers.'
      'google.com/m/cloudstorage/b/[a-z-]+/o/profiler-[a-z0-9-_.]+)@@@',
      re.MULTILINE)

  links = {
      'html-results': html_results_pattern.findall(output),
      'profiler': profiler_pattern.findall(output),
  }

  return links


def _LoadConfigFromString(contents):
  try:
    # The config should be in the following format:
    # config = {'foo': 'foo'}
    # So we really just need to strip off the "config" part.
    json_contents = str(contents).split('{')[1].split('}')[0]
    json_contents = json_contents.replace("'", '\"')
    json_contents = '{%s}' % json_contents
    return json.loads(json_contents)
  except (IndexError, ValueError, AttributeError):
    logging.error('Could not parse config contents: %s', contents)
    return None


def _GetPerfTryResults(job):
  """Gets perf results for a perf try job.

  Args:
    job: TryJob entity.

  Returns:
    A dictionary containing status, results, buildbot_log_url, and
    issue_url for this bisect job, None if perf try job is pending or
    there's an error fetching run data.
  """
  results = {}
  # Fetch bisect bot results from Rietveld server.
  response = _FetchURL(_RietveldIssueJSONURL(job))
  issue_url = _RietveldIssueURL(job)
  try_job_info = _ValidateRietveldResponse(response)

  results['buildbot_log_url'] = str(try_job_info['url'])
  results['issue_url'] = str(issue_url)

  # Check whether the bisect job is finished or not and fetch the output.
  result = int(try_job_info['result'])
  if result not in OK + FAIL:
    return None

  results_url = ('%s/steps/Running%%20Bisection/logs/stdio/text' %
                 try_job_info['url'])
  response = _FetchURL(results_url, skip_status_code=True)
  results['bisect_bot'] = try_job_info['builder']
  results['config'] = _LoadConfigFromString(job.config)

  if not results['config']:
    results['status'] = 'Failure'
    return results

  # We don't see content for "Result" step.  Bot probably did not get there.
  if not response or response.status_code != 200:
    results['status'] = 'Failure'
    return results

  links = _ParseCloudLinksFromOutput(response.content)

  results['html_results'] = (links['html-results'][0]
                             if links['html-results'] else '')
  results['profiler_results'] = links['profiler']
  results['status'] = 'Completed'

  return results


def _CheckBisectJob(job, issue_tracker):
  bisect_results = _GetBisectResults(job)
  if not bisect_results:
    logging.info('No bisect results, job may be pending.')
    return
  logging.info('Bisect job status: %s.', bisect_results['status'])
  if bisect_results['status'] == 'Completed':
    _PostSucessfulResult(job, bisect_results, issue_tracker)
    job.SetCompleted()
  elif bisect_results['status'] == 'Failure with partial results':
    _PostFailedResult(
        job, bisect_results, issue_tracker, add_bug_comment=True)
    job.SetFailed()
  elif bisect_results['status'] == 'Failure':
    _PostFailedResult(job, bisect_results, issue_tracker)
    job.SetFailed()


def _GetBisectResults(job):
  """Gets bisect results for a bisect job.

  Args:
    job: TryJob entity.

  Returns:
    A dictionary containing status, results, buildbot_log_url, and
    issue_url for this bisect job. The issue_url may be a link to a Rietveld
    issue or to Buildbucket job info.
  """
  results = {}
  # Fetch bisect bot results from Rietveld server.
  if job.use_buildbucket:
    try_job_info = _ValidateAndConvertBuildbucketResponse(
        buildbucket_service.GetJobStatus(job.buildbucket_job_id))
    hostname = app_identity.get_default_version_hostname()
    job_id = job.buildbucket_job_id
    issue_url = 'https://%s/buildbucket_job_status/%s' % (hostname, job_id)
  else:
    response = _FetchURL(_RietveldIssueJSONURL(job))
    issue_url = _RietveldIssueURL(job)
    try_job_info = _ValidateRietveldResponse(response)

  results['buildbot_log_url'] = str(try_job_info['url'])
  results['issue_url'] = str(issue_url)

  # Check whether the bisect job is finished or not and fetch the output.
  result = int(try_job_info['result'])
  if result not in OK + FAIL:
    return None

  results_url = '%s/steps/Results/logs/stdio/text' % try_job_info['url']
  response = _FetchURL(results_url, skip_status_code=True)
  results['bisect_bot'] = try_job_info['builder']
  # We don't see content for "Result" step.  Bot probably did not get there.
  if not response or response.status_code != 200:
    results['status'] = 'Failure'
    results['results'] = ''
    build_data = _FetchBuildData(try_job_info['url'])
    if build_data:
      _CheckBisectBotForInfraFailure(job.bug_id, build_data,
                                     try_job_info['url'])
      results['results'] = _GetBotFailureInfo(build_data)
      partial_result = _GetPartialBisectResult(build_data, try_job_info['url'])
      if partial_result:
        results['status'] = 'Failure with partial results'
        results['results'] += partial_result
    return results

  # Clean result.
  # If the bisect_results string contains any non-ASCII characters,
  # converting to string should prevent an error from being raised.
  bisect_result = _BeautifyContent(str(response.content))

  # Bisect is considered success if result is provided.
  # "BISECTION ABORTED" is added when a job is ealy aborted because the
  # associated issue was closed.
  # TODO(robertocn): Make sure we are outputting this string
  if ('BISECT JOB RESULTS' in bisect_result or
      'BISECTION ABORTED' in bisect_result):
    results['status'] = 'Completed'
  else:
    results['status'] = 'Failure'

  results['results'] = bisect_result
  return results


def _FetchBuildData(build_url):
  """Fetches build data from buildbot json api.

  For json api examples see:
  http://build.chromium.org/p/tryserver.chromium.perf/json/help

  Args:
    build_url: URL to a Buildbot bisect tryjob.

  Returns:
    A dictionary of build data for a bisect tryjob. None if there's an
    error fetching build data.
  """
  index = build_url.find('/builders/')
  if index == -1:
    logging.error('Build url does not contain expected "/builders/" to '
                  'fetch json data. URL: %s.', build_url)
    return None

  # Fetch and verify json data.
  json_build_url = build_url[:index] + '/json' + build_url[index:]
  response = _FetchURL(json_build_url)
  if not response:
    logging.error('Could not fetch json data from %s.', json_build_url)
    return None
  try:
    build_data = json.loads(response.content)
    if (not build_data or
        not build_data.get('steps') or
        not build_data.get('times') or
        not build_data.get('text')):
      raise ValueError('Expected properties not found in build data: %s.' %
                       build_data)
  except ValueError, e:
    logging.error('Response from builder could not be parsed as JSON. '
                  'URL: %s. Error: %s.', json_build_url, e)
    return None
  return build_data


def _GetBotFailureInfo(build_data):
  """Returns helpful message about failed bisect runs."""
  message = ''

  # Add success rate message.
  build_steps = build_data['steps']
  num_success_build = 0
  total_build = 0
  for step in build_steps:
    # 'Working on' is the step name for bisect run for a build.
    if 'Working on' in step['name']:
      if step['results'][0] in (SUCCESS, WARNINGS):
        num_success_build += 1
      total_build += 1
  message += 'Completed %s/%s builds.\n' % (num_success_build, total_build)

  # Add run time messsage.
  run_time = build_data['times'][1] - build_data['times'][0]
  run_time = int(run_time / 60)  # Minutes.
  message += 'Run time: %s/%s minutes.\n' % (run_time, _BISECT_BOT_TIMEOUT)
  if run_time >= _BISECT_BOT_TIMEOUT:
    message += 'Bisect timed out! Try again with a smaller revision range.\n'

  # Add failed steps message.
  # 'text' field has the following properties:
  #   text":["failed","slave_steps","failed","Working on [b92af3931458f2]"]
  status_list = build_data['text']
  if status_list[0] == 'failed':
    message += 'Failed steps: %s\n\n' % ', '.join(status_list[1::2])

  return message


def _GetPartialBisectResult(build_data, build_url):
  """Gets partial bisect result if there's any.

  For bisect result output format see:
  https://chromium.googlesource.com/chromium/src/+/master/tools/
  auto_bisect/bisect_perf_regression.py

  Args:
    build_data: A dictionary of build data for a bisect tryjob.
    build_url: URL to a Buildbot bisect tryjob.

  Returns:
    String result of bisect job.
  """
  build_steps = build_data['steps']
  # Search for the last successful bisect step.
  pattern = re.compile(r'===== PARTIAL RESULTS =====(.*)\n\n', re.DOTALL)
  for step in reversed(build_steps):
    # 'Working on' is the step name for bisect run for a build.
    if ('Working on' in step['name'] and
        step['results'][0] in (SUCCESS, WARNINGS)):
      stdio_url = ('%s/steps/%s/logs/stdio/text' %
                   (build_url, urllib.quote(step['name'])))
      response = _FetchURL(stdio_url)
      if response:
        match = pattern.search(response.content)
        if match:
          return _BeautifyContent(match.group())
  return None


def _PostFailedResult(
    job, bisect_results, issue_tracker, add_bug_comment=False):
  """Posts failed bisect results on logger and optional issue tracker."""
  comment = _BUG_COMMENT_TEMPLATE % bisect_results
  if add_bug_comment:
    # Set restrict view label if the bisect results are internal only.
    labels = ['Restrict-View-Google'] if job.internal_only else None
    added_comment = issue_tracker.AddBugComment(
        job.bug_id, comment, labels=labels)
    if not added_comment:
      raise BugUpdateFailure('Failed to update bug %s with comment %s'
                             % (job.bug_id, comment))
  start_try_job.LogBisectResult(job.bug_id, comment)
  logging.info('Updated bug %s with results from %s',
               job.bug_id, job.rietveld_issue_id)


def _PostSucessfulResult(job, bisect_results, issue_tracker):
  """Posts successful bisect results on logger and issue tracker."""
  # From the results, get the list of people to CC (if applicable), the bug
  # to merge into (if applicable) and the commit hash cache key, which
  # will be used below.
  authors_to_cc = []
  merge_issue = None
  bug = ndb.Key('Bug', job.bug_id).get()

  commit_cache_key = _GetCommitHashCacheKey(bisect_results['results'])
  result_is_positive = _BisectResultIsPositive(bisect_results['results'])
  if bug and result_is_positive:
    merge_issue = layered_cache.Get(commit_cache_key)
    if not merge_issue:
      authors_to_cc = _GetAuthorsToCC(bisect_results['results'])

  comment = _BUG_COMMENT_TEMPLATE % bisect_results

  # Add a friendly message to author of culprit CL.
  owner = None
  if authors_to_cc:
    comment = '%s%s' % (_AUTO_ASSIGN_MSG % {'author': authors_to_cc[0]},
                        comment)
    owner = authors_to_cc[0]
  # Set restrict view label if the bisect results are internal only.
  labels = ['Restrict-View-Google'] if job.internal_only else None
  added_comment = issue_tracker.AddBugComment(
      job.bug_id, comment, cc_list=authors_to_cc, merge_issue=merge_issue,
      labels=labels, owner=owner)
  if not added_comment:
    raise BugUpdateFailure('Failed to update bug %s with comment %s'
                           % (job.bug_id, comment))

  start_try_job.LogBisectResult(job.bug_id, comment)
  logging.info('Updated bug %s with results from %s',
               job.bug_id, job.rietveld_issue_id)

  if merge_issue:
    _MapAnomaliesToMergeIntoBug(merge_issue, job.bug_id)
    # Mark the duplicate bug's Bug entity status as closed so that
    # it doesn't get auto triaged.
    bug.status = bug_data.BUG_STATUS_CLOSED
    bug.put()

  # Cache the commit info and bug ID to datastore when there is no duplicate
  # issue that this issue is getting merged into. This has to be done only
  # after the issue is updated successfully with bisect information.
  if commit_cache_key and not merge_issue and result_is_positive:
    layered_cache.Set(commit_cache_key, str(job.bug_id), days_to_keep=30)
    logging.info('Cached bug id %s and commit info %s in the datastore.',
                 job.bug_id, commit_cache_key)


def _ValidateAndConvertBuildbucketResponse(job_info):
  """Checks the response from the buildbucket service and converts it.

  The response is converted to a similar format to that used by Rietveld for
  backwards compatibility.

  Args:
    job_info: A dictionary containing the response from the buildbucket service.

  Returns:
    Try job info dict, guaranteed to have the keys "url" and "result". The aim
    of this method is to return a dict as similar as possible to the result of
    _ValidateRietveldResponse.

  Raises:
    UnexpectedJsonError: The format was not as expected.
  """
  job_info = job_info['build']
  json_response = json.dumps(job_info)
  if not job_info:
    raise UnexpectedJsonError('No response from Buildbucket.')
  if job_info.get('result') is None:
    raise UnexpectedJsonError('No "result" in try job results. '
                              'Buildbucket response: %s' % json_response)
  if job_info.get('url') is None:
    raise UnexpectedJsonError('No "url" in try job results. This could mean '
                              'that the job has not started. '
                              'Buildbucket response: %s' % json_response)
  job_info['builder'] = job_info.get('result_details', {}).get(
      'properties', {}).get('builder_name')
  job_info['result'] = _BuildbucketStatusToStatusConstant(
      job_info['status'], job_info['result'])
  return job_info


def _ValidateRietveldResponse(response):
  """Checks the response from Rietveld to see if the JSON format is right.

  Args:
    response: A Response object, should have a string content attribute.

  Returns:
    Try job info dict, guaranteed to have the keys "url" and "result".

  Raises:
    UnexpectedJsonError: The format was not as expected.
  """
  if not response:
    raise UnexpectedJsonError('No response from Rietveld.')
  try:
    issue_data = json.loads(response.content)
  except ValueError:
    raise UnexpectedJsonError('Response from Rietveld could not be parsed '
                              'as JSON: %s' % response.content)
  # Check whether we can get the results from the issue data response.
  if not issue_data.get('try_job_results'):
    raise UnexpectedJsonError('Empty "try_job_results" in Rietveld response. '
                              'Response: %s.' % response.content)
  try_job_info = issue_data['try_job_results'][0]
  if not try_job_info:
    raise UnexpectedJsonError('Empty item in try job results. '
                              'Rietveld response: %s' % response.content)
  if try_job_info.get('result') is None:
    raise UnexpectedJsonError('No "result" in try job results. '
                              'Rietveld response: %s' % response.content)
  if try_job_info.get('url') is None:
    raise UnexpectedJsonError('No "url" in try job results. This could mean '
                              'that the job has not started. '
                              'Rietveld response: %s' % response.content)
  return try_job_info


def _MapAnomaliesToMergeIntoBug(dest_bug_id, source_bug_id):
  """Maps anomalies from source bug to destination bug.

  Args:
    dest_bug_id: Merge into bug (base bug) number.
    source_bug_id: The bug to be merged.
  """
  query = anomaly.Anomaly.query(
      anomaly.Anomaly.bug_id == int(source_bug_id))
  anomalies = query.fetch()
  for anomaly_entity in anomalies:
    anomaly_entity.bug_id = int(dest_bug_id)
  ndb.put_multi(anomalies)


def _CheckBisectBotForInfraFailure(bug_id, build_data, build_url):
  """Logs bisect failures related to infrastructure.

  Args:
    bug_id: Bug number.
    build_data: A dictionary of build data for a bisect tryjob.
    build_url: URL to a Buildbot bisect tryjob.

  TODO(chrisphan): Remove this once we get an idea of the rate of infra related
                   failures.
  """
  build_steps = build_data['steps']

  # If there's no bisect scripts step then it is considered infra issue.
  slave_step_index = _GetBisectScriptStepIndex(build_steps)
  if not slave_step_index:
    _LogBisectInfraFailure(bug_id, 'Bot failure.', build_url)
    return

  # Timeout failure is our problem.
  run_time = build_data['times'][1] - build_data['times'][0]
  run_time = int(run_time / 60)  # Minutes.
  if run_time >= _BISECT_BOT_TIMEOUT:
    return

  # Any build failure is an infra issue.
  # These flags are output by bisect_perf_regression.py.
  build_failure_flags = [
      'Failed to build revision',
      'Failed to produce build',
      'Failed to perform pre-sync cleanup',
      'Failed to sync',
      'Failed to run [gclient runhooks]',
  ]
  slave_step = build_steps[slave_step_index]
  stdio_url = ('%s/steps/%s/logs/stdio/text' %
               (build_url, urllib.quote(slave_step['name'])))
  response = _FetchURL(stdio_url)
  if response:
    for flag in build_failure_flags:
      if flag in response.content:
        _LogBisectInfraFailure(bug_id, 'Build failure.', build_url)
        return


def _GetBisectScriptStepIndex(build_steps):
  """Gets the index of step that run bisect script in build step data."""
  index = 0
  for step in build_steps:
    if step['name'] in ['slave_steps', 'Running Bisection']:
      return index
    index += 1
  return None


def _LogBisectInfraFailure(bug_id, failure_message, stdio_url):
  """Adds infrastructure related bisect failures to log."""
  comment = failure_message + '\n'
  comment += ('<a href="https://chromeperf.appspot.com/group_report?'
              'bug_id=%s">%s</a>\n' % (bug_id, bug_id))
  comment += 'Buildbot stdio: <a href="%s">%s</a>\n' % (stdio_url, stdio_url)
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('bisect_failures', 'infra', formatter)
  logger.Log(comment)
  logger.Save()


def _BisectResultIsPositive(results_output):
  """Returns True if the bisect found a culprit with high confidence."""
  return 'Status: Positive' in results_output


def _GetCommitHashCacheKey(results_output):
  """Gets a commit hash cache key for the given bisect results output.

  One commit hash key represents a set of culprit CLs. This information is
  stored so in case one issue has the same set of culprit CLs as another,
  in which case one can be marked as duplicate of the other.

  Args:
    results_output: The bisect results output.

  Returns:
    A cache key, less than 500 characters long.
  """
  commits_list = re.findall(r'Commit  : (.*)', results_output)
  commit_hashes = sorted({commit.strip() for commit in commits_list})
  # Generate a cache key by concatenating commit hashes found in bisect
  # results and prepend it with commit_hash.
  commit_cache_key = _COMMIT_HASH_CACHE_KEY % ''.join(commit_hashes)
  # Datastore key name strings must be non-empty strings up to
  # 500 bytes.
  if sys.getsizeof(commit_cache_key) >= 500:
    commit_cache_key = commit_cache_key[:400] + '...'
  return commit_cache_key


def _GetAuthorsToCC(results_output):
  """Makes a list of email addresses that we want to CC on the bug.

  TODO(qyearsley): Make sure that the bisect result bot doesn't cc
  non-googlers on Restrict-View-Google bugs. This might be done by making
  a request for labels for the bug (or by making a request for alerts in
  the datastore for the bug id and checking the internal-only property).

  Args:
    results_output: The bisect results output.

  Returns:
    A list of email addresses, possibly empty.
  """
  author_list = re.findall(r'Author  : (.*)', results_output)
  authors_to_cc = sorted({author.strip() for author in author_list})
  # Avoid CCing issue to multiple authors when bisect finds multiple
  # different authors for culprits CLs.
  if len(authors_to_cc) > 1:
    authors_to_cc = []
  if len(authors_to_cc) == 1:
    # In addition to the culprit CL author, we also want to add reviewers
    # of the culprit CL to the cc list.
    authors_to_cc.extend(_GetReviewersFromBisectLog(results_output))
  return authors_to_cc


def _GetReviewersFromBisectLog(results_output):
  """Parse bisect log and gets reviewers email addresses from Rietveld issue.

  Note: This method doesn't get called when bisect reports multiple CLs by
  different authors, but will get called when there are multiple CLs by the
  same owner.

  Args:
    results_output: Bisect results output.

  Returns:
    List of email addresses from the committed CL.
  """
  reviewer_list = []
  revisions_list = re.findall(r'Link    : (.*)', results_output)
  revisions_links = {rev.strip() for rev in revisions_list}
  # Sometime revision page content consist of multiple "Review URL" strings
  # due to some reverted CLs, such CLs are prefixed with ">"(&gt;) symbols.
  # Should only parse CL link correspoinding the revision found by the bisect.
  link_pattern = (r'(?<!&gt;\s)Review URL: <a href=[\'"]'
                  r'https://codereview.chromium.org/(\d+)[\'"].*>')
  for link in revisions_links:
    # Fetch the commit links in order to get codereview link
    response = _FetchURL(link)
    if not response:
      continue
    rietveld_issue_ids = re.findall(link_pattern, response.content)
    for issue_id in rietveld_issue_ids:
      # Fetch codereview link, and get reviewer email addresses from the
      # response JSON.
      issue_response = _FetchURL(
          'https://codereview.chromium.org/api/%s' % issue_id)
      if not issue_response:
        continue
      issue_data = json.loads(issue_response.content)
      reviewer_list.extend([str(item) for item in issue_data['reviewers']])
  return reviewer_list


def _BeautifyContent(response_data):
  """Strip lines begins with @@@ and strip leading and trailing whitespace."""
  pattern = re.compile(r'@@@.*@@@.*\n')
  response_str = re.sub(pattern, '', response_data)
  new_response = [line.strip() for line in response_str.split('\n')]
  response_str = '\n'.join(new_response)

  delimiter = '---bisect results start here---'
  if delimiter in response_str:
    response_str = response_str.split(delimiter)[1]

  return response_str.rstrip()


def _FetchURL(request_url, skip_status_code=False):
  """Wrapper around URL fetch service to make request.

  Args:
    request_url: URL of request.
    skip_status_code: Skips return code check when True, default is False.

  Returns:
    Response object return by URL fetch, otherwise None when there's an error.
  """
  try:
    response = urlfetch.fetch(request_url)
  except urlfetch_errors.DeadlineExceededError:
    logging.error('Deadline exceeded error checking %s', request_url)
    return None
  except urlfetch_errors.DownloadError as err:
    # DownloadError is raised to indicate a non-specific failure when there
    # was not a 4xx or 5xx status code.
    logging.error(err)
    return None
  if skip_status_code:
    return response
  elif response.status_code != 200:
    logging.error(
        'ERROR %s checking %s', response.status_code, request_url)
    return None
  return response


def _RietveldIssueJSONURL(job):
  config = rietveld_service.GetDefaultRietveldConfig()
  host = config.internal_server_url if job.internal_only else config.server_url
  return '%s/api/%d/%d' % (
      host, job.rietveld_issue_id, job.rietveld_patchset_id)


def _RietveldIssueURL(job):
  config = rietveld_service.GetDefaultRietveldConfig()
  host = config.internal_server_url if job.internal_only else config.server_url
  return '%s/%d' % (host, job.rietveld_issue_id)


def _BuildbucketStatusToStatusConstant(status, result):
  """Converts the string status from buildbucket to a numeric constant."""
  # TODO(robertocn): We might need to make a difference between
  # - Scheduled and Started
  # - Failure and Cancelled.
  if status == 'COMPLETED':
    if result == 'SUCCESS':
      return SUCCESS
    return FAILURE
  return STARTED
