# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Model that represents one bisect or perf test try job.

TryJob entities are checked in /update_bug_from_rietveld to check completed
bisect jobs and update bugs with results.

They are also used in /auto_bisect to restart unsuccessful bisect jobs.
"""

import datetime
import json

from google.appengine.ext import ndb

from dashboard import bisect_stats
from dashboard.models import bug_data


class TryJob(ndb.Model):
  """Stores config and tracking info about a single try job."""
  bot = ndb.StringProperty()
  config = ndb.TextProperty()
  bug_id = ndb.IntegerProperty()
  email = ndb.StringProperty()
  rietveld_issue_id = ndb.IntegerProperty()
  rietveld_patchset_id = ndb.IntegerProperty()
  master_name = ndb.StringProperty(default='ChromiumPerf', indexed=False)
  buildbucket_job_id = ndb.StringProperty()
  use_buildbucket = ndb.BooleanProperty(default=False, indexed=True)

  # TODO(qyearsley) Make this model a subclass of InternalOnlyModel.
  internal_only = ndb.BooleanProperty(default=False, indexed=True)

  # Bisect run status (e.g., started, failed).
  status = ndb.StringProperty(
      default=None,
      choices=['started', 'failed'],
      indexed=True)

  # Number of times this job has been tried.
  run_count = ndb.IntegerProperty(default=0)

  # Last time this job was started.
  last_ran_timestamp = ndb.DateTimeProperty()

  job_type = ndb.StringProperty(
      default='bisect',
      choices=['bisect', 'perf-try'])

  def SetStarted(self):
    self.status = 'started'
    self.run_count += 1
    self.last_ran_timestamp = datetime.datetime.now()
    self.put()
    if self.bug_id:
      bug_data.SetBisectStatus(self.bug_id, 'started')

  def SetFailed(self):
    self.status = 'failed'
    self.put()
    if self.bug_id:
      bug_data.SetBisectStatus(self.bug_id, 'failed')
    bisect_stats.UpdateBisectStats(self.bot, 'failed')

  def SetCompleted(self):
    self.key.delete()
    if self.bug_id:
      bug_data.SetBisectStatus(self.bug_id, 'completed')
    bisect_stats.UpdateBisectStats(self.bot, 'completed')

  def GetConfigDict(self):
    return json.loads(self.config.split('=', 1)[1])
