# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""URL endpoint for a cron job to automatically mark alerts which recovered."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import concurrent.futures
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

from flask import make_response
from google.appengine.ext import ndb

from dashboard.common import datastore_hooks
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import job_state

LOOK_BACK_WEEKS_TOTAL = 104

def UpdatePinpointJobCulpritsPost():
  """Checks if alerts have recovered, and marks them if so.

  This includes checking untriaged alerts, as well as alerts associated with
  open bugs..
  """
  datastore_hooks.SetPrivilegedRequest()

  counter = 0
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    results_map = executor.map(_LookBackAndUpdateJobsWithDiff,
                               list(range(LOOK_BACK_WEEKS_TOTAL)))
    for res in results_map:
      counter += res

  logging.debug('[CULPRITS] In total %d jobs are updated.', counter)

  return make_response('Update finished.')


# Load the weekly changes for Pinpoint jobs between (now - look_back_weeks)
# and (now - look_back_weeks - 1). If the job has difference_count > 0, try
# to load the difference info from job state, and populate the commit info
# into a new column 'culprits'.
def _LookBackAndUpdateJobsWithDiff(look_back_weeks):
  current = datetime.now() - relativedelta(weeks=look_back_weeks)
  one_week_ago = current - relativedelta(weeks=1)

  # Fetch the jobs for the month, which are bisection jobs, with different
  # count > 0, and no culprits are been populated yet.
  query = job_module.Job.query()
  query = query.filter(job_module.Job.created > one_week_ago)
  query = query.filter(job_module.Job.created < current)
  query = query.filter(job_module.Job.comparison_mode == job_state.PERFORMANCE)
  jobs = query.fetch()

  logging.debug('[CULPRITS] Loaded %d bisect jobs between %s and %s.',
                len(jobs), one_week_ago.date(), current.date())
  # skip the jobs which has no difference.
  jobs = [j for j in jobs if j.difference_count and j.difference_count > 0]
  logging.debug('[CULPRITS] Loaded %d jobs with DIFF.', len(jobs))
  # TODO(b/406405606): uncomment to skip the jobs which has been backfilled.
  # jobs = [j for j in jobs if j.culprits == []]
  # logging.debug('[CULPRITS] Loaded %d jobs with no culprits.', len(jobs))

  jobs_to_update = []
  for job in jobs:
    culprits = []
    state = job.state
    differences = state.Differences()
    logging.debug(
        '[CULPRITS] Processing job %s with %d differences and culprits: %s',
        job.key.id, len(differences), job.culprits)

    if len(differences) == 0:
      logging.warning(
          '[CULPRITS] Job %s has diff count %d but has no difference in state.',
          job.key.id, job.difference_count)
      continue

    for commit_pair in differences:
      # The second Commit from the 'difference' is one caused the change.
      culprit = commit_pair[1].AsDict()
      # For those with drilldowns, we may have multiple commits from different
      # repo. The last commit is the one we report.
      commit = culprit['commits'][-1]
      logging.debug('[CULPRITS] ID: %s, Culprit: %s', job.key.id, commit)

      repo = commit.get('repository')
      git_hash = commit.get('git_hash')
      if not repo or not git_hash:
        logging.warning(
            '[CULPRITS] Culprit commit does not have repo (%s) or hash (%s)',
            repo, git_hash)
        continue
      culprits.append('%s/%s' % (repo, git_hash))

    logging.debug('[CULPRITS] Adding culprits %s to Pinpoint job %s', culprits,
                  job.key.id)
    job.culprits = culprits
    jobs_to_update.append(job)

  logging.debug('[CULPRITS] Batch saving %d jobs. (%s to %s.)',
                len(jobs_to_update), one_week_ago.date(), current.date())
  ndb.put_multi(jobs_to_update)

  return len(jobs_to_update)
