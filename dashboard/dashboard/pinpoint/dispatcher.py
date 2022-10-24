# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Dispatches requests to request handler classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

# crbug/1339701
# This is a hack to force ndb to use a lower version of pickle protocol when
# creating job state data, which be loaded in both Python 2 and 3 runtime.
# This workaround assumes ndb will not set HIGHEST_PROTOCOL at any point.
# Otherwise, it will break that the pinpoint service running in Python 2 runtime
# can no longer load the jobs created in Python 3.
# This hack will be relied on only during the transition time to Python 3. It
# will allow fallback to Python 2 if needed.
import pickle
pickle.HIGHEST_PROTOCOL = 2

import sys

from dashboard.common import utils
from dashboard.pinpoint import handlers

if utils.IsRunningFlask():

  from flask import Flask
  APP = Flask(__name__)

  if sys.version_info.major == 3:
    from google.appengine.api import wrap_wsgi_app
    APP.wsgi_app = wrap_wsgi_app(APP.wsgi_app, use_deferred=True)

  @APP.route('/api/jobs')
  def JobsHandlerGet():
    return handlers.jobs.JobsHandlerGet()

  @APP.route('/api/config', methods=['POST'])
  def ConfigHandlerPost():
    return handlers.config.ConfigHandlerPost()

  @APP.route('/api/commit', methods=['POST'])
  def CommitHandlerPost():
    return handlers.commit.CommitHandlerPost()

  @APP.route('/api/new', methods=['POST'])
  def NewHandlerPost():
    return handlers.new.NewHandlerPost()

  @APP.route('/api/job/<job_id>')
  def JobHandlerGet(job_id):
    return handlers.job.JobHandlerGet(job_id)

  @APP.route('/api/queue-stats/<configuration>')
  def QueueStatsHandlerGet(configuration):
    return handlers.queue_stats.QueueStatsHandlerGet(configuration)

  @APP.route('/api/job/cancel', methods=['POST'])
  def CancelHandlerPost():
    return handlers.cancel.CancelHandlerPost()

  @APP.route('/api/commits', methods=['POST'])
  def CommitsHandlerPost():
    return handlers.commits.CommitsHandlerPost()

  @APP.route('/api/migrate', methods=['GET', 'POST'])
  def MigrateHandler():
    return handlers.migrate.MigrateHandler()

  # Used internally by Pinpoint. Not accessible from the public API
  @APP.route('/cron/fifo-scheduler')
  def FifoSchedulerHandler():
    return handlers.fifo_scheduler.FifoSchedulerHandler()

  @APP.route('/cron/refresh-jobs')
  def RefreshJobsHandler():
    return handlers.refresh_jobs.RefreshJobsHandler()

  @APP.route('/cron/isolate-cleanup')
  def IsolateCleanupHandler():
    return handlers.isolate.IsolateCleanupHandler()

  @APP.route('/api/results2/<job_id>')
  def Results2Handler(job_id):
    return handlers.results2.Results2Handler(job_id)

  @APP.route('/api/generate-results2/<job_id>', methods=['POST'])
  def Results2GeneratorHandler(job_id):
    return handlers.results2.Results2GeneratorHandler(job_id)

  @APP.route('/api/run/<job_id>', methods=['POST'])
  def RunHandler(job_id):
    return handlers.run.RunHandler(job_id)

  @APP.route('/api/isolate', methods=['GET', 'POST'])
  def IsolateHandler():
    return handlers.isolate.IsolateHandler()

  @APP.route('/api/stats')
  def StatsHandler():
    return handlers.stats.StatsHandler()

  @APP.route('/_ah/push-handlers/task-updates', methods=['POST'])
  def TaskUpdatesHandler():
    return handlers.task_updates.TaskUpdatesHandler()

else:
  import webapp2

  _URL_MAPPING = [
      # Public API.
      webapp2.Route(r'/api/config', handlers.Config),
      webapp2.Route(r'/api/commit', handlers.Commit),
      webapp2.Route(r'/api/commits', handlers.Commits),
      webapp2.Route(r'/api/generate-results2/<job_id>',
                    handlers.Results2Generator),
      webapp2.Route(r'/api/isolate', handlers.Isolate),
      webapp2.Route(r'/api/isolate/<builder_name>/<git_hash>/<target>',
                    handlers.CASReference),
      webapp2.Route(r'/api/cas', handlers.CASReference),
      webapp2.Route(r'/api/cas/<builder_name>/<git_hash>/<target>',
                    handlers.CASReference),
      webapp2.Route(r'/api/job/cancel', handlers.Cancel),
      webapp2.Route(r'/api/job/<job_id>', handlers.Job),
      webapp2.Route(r'/api/jobs', handlers.Jobs),
      webapp2.Route(r'/api/migrate', handlers.Migrate),
      webapp2.Route(r'/api/new', handlers.New),
      webapp2.Route(r'/api/results2/<job_id>', handlers.Results2),
      webapp2.Route(r'/api/stats', handlers.Stats),
      webapp2.Route(r'/api/queue-stats/<configuration>', handlers.QueueStats),

      # Used internally by Pinpoint. Not accessible from the public API.
      webapp2.Route(r'/api/run/<job_id>', handlers.Run),
      webapp2.Route(r'/cron/isolate-cleanup', handlers.IsolateCleanup),
      webapp2.Route(r'/cron/refresh-jobs', handlers.RefreshJobs),
      webapp2.Route(r'/cron/fifo-scheduler', handlers.FifoScheduler),

      # The /_ah/push-handlers/* paths have a special meaning for PubSub
      # notifications, and is treated especially by the AppEngine environment.
      webapp2.Route(r'/_ah/push-handlers/task-updates', handlers.TaskUpdates),
  ]

  APP = webapp2.WSGIApplication(_URL_MAPPING, debug=False)
