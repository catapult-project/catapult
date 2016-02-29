# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to update bugs after bisects."""

import datetime
import json
import logging
import re
import traceback

from google.appengine.api import mail
from google.appengine.ext import ndb

from dashboard import bisect_fyi
from dashboard import bisect_report
from dashboard import datastore_hooks
from dashboard import email_template
from dashboard import issue_tracker_service
from dashboard import layered_cache
from dashboard import quick_logger
from dashboard import request_handler
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models import try_job

COMPLETED, FAILED, PENDING, ABORTED = ('completed', 'failed', 'pending',
                                       'aborted')

_COMMIT_HASH_CACHE_KEY = 'commit_hash_%s'

# Amount of time to pass before deleting a try job.
_STALE_TRYJOB_DELTA = datetime.timedelta(days=7)

_AUTO_ASSIGN_MSG = """
=== Auto-CCing suspected CL author %(author)s ===

Hi %(author)s, the bisect results pointed to your CL below as possibly
causing a regression. Please have a look at this info and see whether
your CL be related.

"""

_CONFIDENCE_LEVEL_TO_CC_AUTHOR = 95


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
    credentials = utils.ServiceAccountCredentials()
    issue_tracker = issue_tracker_service.IssueTrackerService(
        additional_credentials=credentials)

    # Set privilege so we can also fetch internal try_job entities.
    datastore_hooks.SetPrivilegedRequest()

    jobs_to_check = try_job.TryJob.query(
        try_job.TryJob.status.IN(['started', 'pending'])).fetch()
    all_successful = True

    for job in jobs_to_check:
      try:
        _CheckJob(job, issue_tracker)
      except Exception as e:  # pylint: disable=broad-except
        logging.error('Caught Exception %s: %s\n%s',
                      type(e).__name__, e, traceback.format_exc())
        all_successful = False

    if all_successful:
      utils.TickMonitoringCustomMetric('UpdateBugWithResults')


def _CheckJob(job, issue_tracker):
  """Checks whether a try job is finished and updates a bug if applicable.

  This method returns nothing, but it may log errors.

  Args:
    job: A TryJob entity, which represents one bisect try job.
    issue_tracker: An issue_tracker_service.IssueTrackerService instance.
  """
  if _IsStale(job):
    job.SetStaled()
    # TODO(chrisphan): Add a staled TryJob log.
    # TODO(chrisphan): Do we want to send a FYI Bisect email here?
    return

  results_data = job.results_data
  if not results_data or results_data['status'] not in [COMPLETED, FAILED]:
    return

  if job.job_type == 'perf-try':
    _SendPerfTryJobEmail(job)
  elif job.job_type == 'bisect-fyi':
    _CheckFYIBisectJob(job, issue_tracker)
  else:
    _CheckBisectJob(job, issue_tracker)

  if results_data['status'] == COMPLETED:
    job.SetCompleted()
  else:
    job.SetFailed()


def _CheckBisectJob(job, issue_tracker):
  results_data = job.results_data
  has_partial_result = ('revision_data' in results_data and
                        results_data['revision_data'])
  if results_data['status'] == FAILED and not has_partial_result:
    return
  _PostResult(job, issue_tracker)


def _CheckFYIBisectJob(job, issue_tracker):
  try:
    _PostResult(job, issue_tracker)
    error_message = bisect_fyi.VerifyBisectFYIResults(job)
    if not bisect_fyi.IsBugUpdated(job, issue_tracker):
      error_message += '\nFailed to update bug with bisect results.'
  except BugUpdateFailure as e:
    error_message = 'Failed to update bug with bisect results: %s' % e
  if job.results_data['status'] == FAILED or error_message:
    _SendFYIBisectEmail(job, error_message)


def _SendPerfTryJobEmail(job):
  """Sends an email to the user who started the perf try job."""
  if not job.email:
    return
  email_report = email_template.GetPerfTryJobEmailReport(job)
  if not email_report:
    return
  mail.send_mail(sender='gasper-alerts@google.com',
                 to=job.email,
                 subject=email_report['subject'],
                 body=email_report['body'],
                 html=email_report['html'])


def _PostResult(job, issue_tracker):
  """Posts bisect results on issue tracker."""
  # From the results, get the list of people to CC (if applicable), the bug
  # to merge into (if applicable) and the commit hash cache key, which
  # will be used below.
  if job.bug_id < 0:
    return

  results_data = job.results_data
  authors_to_cc = []
  commit_cache_key = _GetCommitHashCacheKey(results_data)

  merge_issue = layered_cache.GetExternal(commit_cache_key)
  if not merge_issue:
    authors_to_cc = _GetAuthorsToCC(results_data)

  comment = bisect_report.GetReport(job)

  # Add a friendly message to author of culprit CL.
  owner = None
  if authors_to_cc:
    comment = '%s%s' % (_AUTO_ASSIGN_MSG % {'author': authors_to_cc[0]},
                        comment)
    owner = authors_to_cc[0]
  # Set restrict view label if the bisect results are internal only.
  labels = ['Restrict-View-Google'] if job.internal_only else None
  comment_added = issue_tracker.AddBugComment(
      job.bug_id, comment, cc_list=authors_to_cc, merge_issue=merge_issue,
      labels=labels, owner=owner)
  if not comment_added:
    raise BugUpdateFailure('Failed to update bug %s with comment %s'
                           % (job.bug_id, comment))

  logging.info('Updated bug %s with results from %s',
               job.bug_id, job.rietveld_issue_id)

  if merge_issue:
    _MapAnomaliesToMergeIntoBug(merge_issue, job.bug_id)
    # Mark the duplicate bug's Bug entity status as closed so that
    # it doesn't get auto triaged.
    bug = ndb.Key('Bug', job.bug_id).get()
    if bug:
      bug.status = bug_data.BUG_STATUS_CLOSED
      bug.put()

  # Cache the commit info and bug ID to datastore when there is no duplicate
  # issue that this issue is getting merged into. This has to be done only
  # after the issue is updated successfully with bisect information.
  if commit_cache_key and not merge_issue:
    layered_cache.SetExternal(commit_cache_key, str(job.bug_id),
                              days_to_keep=30)
    logging.info('Cached bug id %s and commit info %s in the datastore.',
                 job.bug_id, commit_cache_key)


def _IsStale(job):
  if not job.last_ran_timestamp:
    return False
  time_since_last_ran = datetime.datetime.now() - job.last_ran_timestamp
  return time_since_last_ran > _STALE_TRYJOB_DELTA


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


def _GetCommitHashCacheKey(results_data):
  """Gets a commit hash cache key for the given bisect results output.

  Args:
    results_data: Bisect results data.

  Returns:
    A string to use as a layered_cache key, or None if we don't want
    to merge any bugs based on this bisect result.
  """
  if results_data.get('culprit_data'):
    return _COMMIT_HASH_CACHE_KEY % results_data['culprit_data']['cl']
  return None


def _GetAuthorsToCC(results_data):
  """Makes a list of email addresses that we want to CC on the bug.

  TODO(qyearsley): Make sure that the bisect result bot doesn't cc
  non-googlers on Restrict-View-Google bugs. This might be done by making
  a request for labels for the bug (or by making a request for alerts in
  the datastore for the bug id and checking the internal-only property).

  Args:
    results_data: Bisect results data.

  Returns:
    A list of email addresses, possibly empty.
  """
  if results_data.get('score') < _CONFIDENCE_LEVEL_TO_CC_AUTHOR:
    return []
  culprit_data = results_data.get('culprit_data')
  if not culprit_data:
    return []
  emails = [culprit_data['email']] if culprit_data['email'] else []
  emails.extend(_GetReviewersFromCulpritData(culprit_data))
  return emails


def _GetReviewersFromCulpritData(culprit_data):
  """Parse bisect log and gets reviewers email addresses from Rietveld issue.

  Note: This method doesn't get called when bisect reports multiple CLs by
  different authors, but will get called when there are multiple CLs by the
  same owner.

  Args:
    culprit_data: Bisect results culprit data.

  Returns:
    List of email addresses from the committed CL.
  """

  reviewer_list = []
  revisions_links = culprit_data['revisions_links']
  # Sometime revision page content consist of multiple "Review URL" strings
  # due to some reverted CLs, such CLs are prefixed with ">"(&gt;) symbols.
  # Should only parse CL link corresponding the revision found by the bisect.
  link_pattern = (r'(?<!&gt;\s)Review URL: <a href=[\'"]'
                  r'https://codereview.chromium.org/(\d+)[\'"].*>')
  for link in revisions_links:
    # Fetch the commit links in order to get codereview link.
    response = utils.FetchURL(link)
    if not response:
      continue
    rietveld_issue_ids = re.findall(link_pattern, response.content)
    for issue_id in rietveld_issue_ids:
      # Fetch codereview link, and get reviewer email addresses from the
      # response JSON.
      issue_response = utils.FetchURL(
          'https://codereview.chromium.org/api/%s' % issue_id)
      if not issue_response:
        continue
      issue_data = json.loads(issue_response.content)
      reviewer_list.extend([str(item) for item in issue_data['reviewers']])
  return reviewer_list


def _SendFYIBisectEmail(job, message):
  """Sends an email to auto-bisect-team about FYI bisect results."""
  email_data = email_template.GetBisectFYITryJobEmailReport(job, message)
  mail.send_mail(sender='gasper-alerts@google.com',
                 to='auto-bisect-team@google.com',
                 subject=email_data['subject'],
                 body=email_data['body'],
                 html=email_data['html'])


def UpdateQuickLog(job):
  if not job.bug_id or job.bug_id < 0:
    return
  report = bisect_report.GetReport(job)
  if not report:
    logging.error('Bisect report returns empty for job id %s, bug_id %s.',
                  job.key.id(), job.bug_id)
    return
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('bisect_result', job.bug_id, formatter)
  if job.log_record_id:
    logger.Log(report, record_id=job.log_record_id)
    logger.Save()
  else:
    job.log_record_id = logger.Log(report)
    logger.Save()
    job.put()
