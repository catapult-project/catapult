# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Dispatches requests to request handler classes."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.common import utils
from dashboard.pinpoint import handlers

if utils.IsRunningFlask():
  from flask import Flask

  APP = Flask(__name__)

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
