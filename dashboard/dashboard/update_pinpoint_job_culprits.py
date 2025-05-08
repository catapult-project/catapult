# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""URL endpoint for a cron job to automatically mark alerts which recovered."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

from flask import make_response

from dashboard.common import datastore_hooks
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import job_state


def UpdatePinpointJobCulpritsPost():
  """Checks if alerts have recovered, and marks them if so.

  This includes checking untriaged alerts, as well as alerts associated with
  open bugs..
  """
  datastore_hooks.SetPrivilegedRequest()

  query = job_module.Job.query()
  two_years_ago = datetime.now() - relativedelta(years=2)
  query = query.filter(job_module.Job.created > two_years_ago)
  query = query.filter(job_module.Job.comparison_mode == job_state.PERFORMANCE)
  jobs = query.order(-job_module.Job.created).fetch()

  logging.debug('[CULPRITS] Loaded %d bisect jobs in the last 2 years.',
                len(jobs))
  jobs = [j for j in jobs if j.difference_count and j.difference_count > 0]
  logging.debug('[CULPRITS] Loaded %d jobs with DIFF.', len(jobs))
  jobs = [j for j in jobs if j.culprits == []]
  logging.debug('[CULPRITS] Loaded %d jobs with no culprits.', len(jobs))

  culprits = []
  for job in jobs:
    state = job.state
    differences = state.Differences()
    logging.debug('[CULPRITS] Processing job %s with %d differences',
                  job.key.id, len(differences))
    for commit_pair in differences:
      culprit = commit_pair[1].AsDict()
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
    job.put()
    # TODO (b/416555830) Start with backfilling culprits on one job per call,
    # for debuggning purposes.
    break

  return make_response('')
